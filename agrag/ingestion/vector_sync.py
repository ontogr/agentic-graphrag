"""Synchronize graph-owned embeddings with an external vector store."""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any, TypeAlias
from uuid import UUID

from opentelemetry.trace import Tracer

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.community import COMMUNITY_LABEL, Community
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import DeferredWrites
from agrag.common.data_models.resolved_entity import (
    ResolvedEntity,
)
from agrag.common.data_models.stage_failure import StageFailure
from agrag.common.data_models.vector_record import (
    VectorKind,
    VectorRecord,
    VectorRepairCounts,
    VectorRepairResult,
    VectorTarget,
)
from agrag.common.graph_rows import node_properties
from agrag.cypher.community_read import hydrate_communities_by_id_query
from agrag.cypher.entities import load_chunks_by_id_query
from agrag.cypher.resolution_read import load_resolved_entities_for_sync_query
from agrag.cypher.resolution_write import set_resolved_entity_sync_status_query
from agrag.cypher.vector_targets import (
    committed_vector_ids_query,
    existing_ids_query,
    node_labels_query,
    vector_target_check_query,
)
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.graphdb.entities import load_entities
from agrag.observability import get_tracer, record_stage_failure
from agrag.retrieval.chunking import parse_chunk_node
from agrag.vectordb.base import VectorStore


VectorItem: TypeAlias = tuple[UUID, list[str], str, Mapping[str, str]]
_BATCH_SIZE = 256
_PAGE_SIZE = 1000


class VectorSync:
    """Own guarded embedding, deletion and repair operations for one graph."""

    def __init__(
        self,
        *,
        store: VectorStore,
        embedder: Embedder,
        graph_store: GraphStore,
        tracer: Tracer | None = None,
        embed_heading_path: bool = True,
    ) -> None:
        """Bind the graph, embedder and external store used by sync operations.

        ``embed_heading_path`` keeps chunk re-syncs consistent with ingestion.
        """
        self.store = store
        self.embedder = embedder
        self.graph_store = graph_store
        self.tracer = get_tracer(tracer)
        self.embed_heading_path = embed_heading_path

    async def upsert_owned(
        self,
        kind: VectorKind,
        items: Sequence[VectorItem],
        *,
        job_id: UUID | str | None,
        deferred: DeferredWrites | None,
    ) -> list[UUID]:
        """Embed and upsert eligible rows, deferring committed rows in a job.

        Rows are rechecked against their graph ownership and embedding text
        before embedding. Committed rows reached by a job are recorded for
        post-commit synchronization instead of being written early.
        """
        if job_id is not None and deferred is None:
            raise ValueError("deferred is required when job_id is set")
        if not items:
            return []
        job_id_value = str(job_id) if job_id is not None else None
        records: list[UUID] = []
        for start in range(0, len(items), _BATCH_SIZE):
            batch = items[start : start + _BATCH_SIZE]
            rows = [
                {
                    "id": str(item_id),
                    "pending_job_id": job_id_value,
                    **guard_fields,
                }
                for item_id, _labels, _text, guard_fields in batch
            ]
            checked = await self.graph_store.execute_read(
                vector_target_check_query(kind), {"rows": rows}
            )
            by_id = {str(row["id"]): row for row in checked}
            eligible: list[tuple[UUID, list[str], str]] = []
            for item_id, labels, text, _guard_fields in batch:
                result = by_id.get(str(item_id))
                if result is None:
                    continue
                if result["state"] == "committed" and deferred is not None:
                    target = VectorTarget(kind=kind, id=item_id)
                    if target not in deferred.vector_targets:
                        deferred.vector_targets.append(target)
                    continue
                node_labels = [str(label) for label in result.get("labels", [])]
                eligible.append((item_id, node_labels or labels, text))
            if not eligible:
                continue
            vectors = await self.embedder.embed([item[2] for item in eligible])
            vector_records = [
                VectorRecord(
                    id=item_id,
                    vector=vector,
                    labels=labels,
                    text=text,
                )
                for (item_id, labels, text), vector in zip(
                    eligible, vectors, strict=True
                )
            ]
            await self.store.upsert(kind, vector_records, batch_size=_BATCH_SIZE)
            records.extend(item.id for item in vector_records)
        return records

    async def sync_committed(
        self, targets: Sequence[VectorTarget]
    ) -> list[StageFailure]:
        """Re-embed committed targets from their current graph state.

        Missing rows and rows that change during embedding are skipped. A
        failure in one batch is returned without preventing later batches.
        """
        _successful, failures = await self._sync_committed(targets)
        return failures

    async def delete_absent(
        self, kind: VectorKind, candidate_ids: Sequence[UUID]
    ) -> int:
        """Delete vectors with absent graph nodes and return the removed count."""
        unique_ids = list(dict.fromkeys(candidate_ids))
        deleted = 0
        for start in range(0, len(unique_ids), _BATCH_SIZE):
            batch = unique_ids[start : start + _BATCH_SIZE]
            rows = await self.graph_store.execute_read(
                existing_ids_query(kind), {"ids": [str(item) for item in batch]}
            )
            existing = {UUID(str(row["id"])) for row in rows}
            absent = [item for item in batch if item not in existing]
            if absent:
                await self.store.delete(kind, absent)
                deleted += len(absent)
        return deleted

    async def replace_communities(
        self, communities: Sequence[Community], *, old_ids: Sequence[UUID]
    ) -> None:
        """Upsert replacement community vectors and remove absent old vectors."""
        items = [
            (
                community.id,
                [COMMUNITY_LABEL],
                community.embedding_text,
                {
                    "expected_title": community.title,
                    "expected_summary": community.summary,
                },
            )
            for community in communities
        ]
        failure: Exception | None = None
        try:
            await self.upsert_owned(
                VectorKind.COMMUNITY, items, job_id=None, deferred=None
            )
        except Exception as exc:  # noqa: BLE001
            failure = exc
        await self.delete_absent(VectorKind.COMMUNITY, old_ids)
        if failure is not None:
            raise failure

    async def repair(
        self,
        kinds: Sequence[VectorKind] | None = None,
        *,
        prune: bool = False,
    ) -> VectorRepairResult:
        """Restore missing vectors and optionally delete store-only ids."""
        result = VectorRepairResult()
        selected_kinds = tuple(VectorKind) if kinds is None else tuple(kinds)
        for kind in selected_kinds:
            graph_ids = await self._graph_ids(kind)
            store_ids = await self._store_ids(kind)
            missing = sorted(graph_ids - store_ids, key=str)
            counts = VectorRepairCounts(checked=len(graph_ids), missing=len(missing))
            successes, failures = await self._sync_committed(
                [VectorTarget(kind=kind, id=item_id) for item_id in missing]
            )
            counts.upserted = len(successes.get(kind, set()))
            counts.failures.extend(failures)
            if prune:
                orphaned = sorted(store_ids - graph_ids, key=str)
                for start in range(0, len(orphaned), _BATCH_SIZE):
                    batch = orphaned[start : start + _BATCH_SIZE]
                    try:
                        counts.pruned += await self.delete_absent(kind, batch)
                    except Exception as exc:  # noqa: BLE001
                        counts.failures.append(_failure(exc, batch))
                        break
            result.kinds[kind] = counts
        return result

    async def _sync_committed(
        self, targets: Sequence[VectorTarget]
    ) -> tuple[dict[VectorKind, set[UUID]], list[StageFailure]]:
        """Run committed sync and retain successful ids for repair counts."""
        grouped: dict[VectorKind, list[UUID]] = defaultdict(list)
        for target in targets:
            grouped[target.kind].append(target.id)
        successes: dict[VectorKind, set[UUID]] = defaultdict(set)
        failures: list[StageFailure] = []
        for kind, ids in grouped.items():
            unique_ids = list(dict.fromkeys(ids))
            for start in range(0, len(unique_ids), _BATCH_SIZE):
                batch_ids = unique_ids[start : start + _BATCH_SIZE]
                try:
                    models = await self._load(kind, batch_ids)
                    if not models:
                        continue
                    labels = await self._labels(list(models))
                    items = [
                        self._item(kind, model, labels.get(item_id, []))
                        for item_id, model in models.items()
                    ]
                    written = await self.upsert_owned(
                        kind, items, job_id=None, deferred=None
                    )
                    successes[kind].update(written)
                    if kind is VectorKind.RESOLVED_ENTITY and written:
                        await self._set_resolved_status(written, "synced")
                except Exception as exc:  # noqa: BLE001
                    failures.append(_failure(exc, batch_ids))
                    if kind is VectorKind.RESOLVED_ENTITY:
                        await self._set_resolved_status(
                            batch_ids, "failed", error=str(exc)
                        )
        return successes, failures

    async def _load(
        self, kind: VectorKind, ids: Sequence[UUID]
    ) -> dict[UUID, Chunk | Entity | ResolvedEntity | Community]:
        """Load committed models needed to rebuild one collection batch."""
        id_strings = [str(item_id) for item_id in ids]
        if kind is VectorKind.CHUNK:
            rows = await self.graph_store.execute_read(
                load_chunks_by_id_query(), {"ids": id_strings, "job_id": None}
            )
            return {
                chunk.id: chunk
                for row in rows
                if (chunk := parse_chunk_node(row.get("n"))) is not None
                and chunk.id is not None
            }
        if kind is VectorKind.ENTITY:
            entities = await load_entities(self.graph_store, ids, tracer=self.tracer)
            return dict(entities)
        if kind is VectorKind.RESOLVED_ENTITY:
            rows = await self.graph_store.execute_read(
                load_resolved_entities_for_sync_query(), {"ids": id_strings}
            )
            return {
                entity.id: entity
                for row in rows
                if (entity := _resolved_entity(row.get("resolved"))) is not None
            }
        rows = await self.graph_store.execute_read(
            hydrate_communities_by_id_query(), {"ids": id_strings}
        )
        return {
            community.id: community
            for row in rows
            if (community := _community(row.get("n"))) is not None
        }

    async def _labels(self, ids: Sequence[UUID]) -> dict[UUID, list[str]]:
        """Read external searchable labels, including entity ancestors."""
        if not ids:
            return {}
        rows = await self.graph_store.execute_read(
            node_labels_query(), {"ids": [str(item_id) for item_id in ids]}
        )
        return {
            UUID(str(row["id"])): [str(label) for label in row.get("labels", [])]
            for row in rows
        }

    def _item(
        self,
        kind: VectorKind,
        model: Chunk | Entity | ResolvedEntity | Community,
        labels: list[str],
    ) -> VectorItem:
        """Build a guarded sync item from one loaded graph model."""
        if kind is VectorKind.CHUNK and isinstance(model, Chunk):
            if model.id is None:
                raise ValueError("Stored chunk is missing its id")
            text = model.contextual_text if self.embed_heading_path else model.text
            return model.id, labels, text, {"expected_text": model.text}
        if kind is VectorKind.ENTITY and isinstance(model, Entity):
            description = model.properties.get("description")
            return (
                model.id,
                labels,
                model.embedding_text,
                {
                    "expected_name": model.name,
                    "expected_description": str(description) if description else "",
                },
            )
        if kind is VectorKind.RESOLVED_ENTITY and isinstance(model, ResolvedEntity):
            description = model.properties.get("description")
            return (
                model.id,
                labels,
                model.embedding_text,
                {
                    "expected_name": model.name,
                    "expected_description": str(description) if description else "",
                },
            )
        if kind is VectorKind.COMMUNITY and isinstance(model, Community):
            return (
                model.id,
                labels,
                model.embedding_text,
                {
                    "expected_title": model.title,
                    "expected_summary": model.summary,
                },
            )
        raise TypeError(f"Loaded model does not match vector kind {kind}")

    async def _graph_ids(self, kind: VectorKind) -> set[UUID]:
        """Read every committed graph id for a collection by keyset pages."""
        ids: set[UUID] = set()
        after: UUID | None = None
        while True:
            rows = await self.graph_store.execute_read(
                committed_vector_ids_query(kind),
                {
                    "after": str(after) if after is not None else None,
                    "limit": _PAGE_SIZE,
                },
            )
            page = [UUID(str(row["id"])) for row in rows]
            ids.update(page)
            if len(page) < _PAGE_SIZE:
                return ids
            after = page[-1]

    async def _store_ids(self, kind: VectorKind) -> set[UUID]:
        """Read every collection id through the store's keyset interface."""
        ids: set[UUID] = set()
        after: UUID | None = None
        while True:
            page = await self.store.list_ids(kind, after=after, limit=_PAGE_SIZE)
            if not page:
                return ids
            ids.update(page)
            if len(page) < _PAGE_SIZE:
                return ids
            after = page[-1]

    async def _set_resolved_status(
        self,
        ids: Sequence[UUID],
        status: str,
        *,
        error: str | None = None,
    ) -> None:
        """Persist resolved-entity vector status for ids that still exist."""
        if not ids:
            return
        await self.graph_store.execute_write(
            set_resolved_entity_sync_status_query(),
            {
                "records": [
                    {"id": str(item_id), "status": status, "error": error}
                    for item_id in ids
                ]
            },
        )


def _resolved_entity(row: object) -> ResolvedEntity | None:
    """Parse a resolved entity row without filtering by its sync status."""
    properties = node_properties(row)
    item_id = properties.get("id")
    if item_id is None:
        return None
    system_keys = {
        "id",
        "name",
        "label",
        "member_ids",
        "created_at",
        "vector_sync_status",
        "vector_sync_error",
        "embedding",
    }
    values: dict[str, Any] = {
        key: value for key, value in properties.items() if key in system_keys
    }
    values["properties"] = {
        key: value for key, value in properties.items() if key not in system_keys
    }
    try:
        return ResolvedEntity.model_validate(values)
    except (TypeError, ValueError):
        return None


def _community(row: object) -> Community | None:
    """Parse a community row for external vector synchronization."""
    properties = node_properties(row)
    item_id = properties.get("id")
    if item_id is None:
        return None
    try:
        return Community(
            id=UUID(str(item_id)),
            title=str(properties.get("title", "")),
            summary=str(properties.get("summary", "")),
            rating=float(properties.get("rating", 0.0)),
            rating_explanation=str(properties.get("rating_explanation", "")),
            findings=list(properties.get("findings") or []),
            member_ids=[UUID(str(item)) for item in properties.get("member_ids", [])],
            internal_weight=float(properties.get("internal_weight", 0.0)),
        )
    except (TypeError, ValueError):
        return None


def _failure(error: Exception, ids: Sequence[UUID]) -> StageFailure:
    """Build one trace-linked failure for a vector-sync batch."""
    trace_id, span_id = record_stage_failure(error)
    return StageFailure(
        item_id=",".join(str(item_id) for item_id in ids),
        error_type=type(error).__name__,
        error_message=str(error),
        trace_id=trace_id,
        span_id=span_id,
    )
