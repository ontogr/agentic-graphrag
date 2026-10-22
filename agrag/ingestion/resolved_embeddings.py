"""Embedding writes and sync status for resolved entities."""

import contextlib
from typing import Literal
from uuid import UUID

from agrag.common.data_models.graph_record import DeferredWrites
from agrag.common.data_models.resolved_entity import (
    RESOLVED_ENTITY_LABEL,
    ResolvedEntity,
)
from agrag.common.data_models.stage_failure import StageFailure
from agrag.common.data_models.vector_record import VectorKind
from agrag.cypher.entities import clear_property_query, set_embedding_query
from agrag.cypher.resolution_write import set_resolved_entity_sync_status_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion._deferred import write_or_defer
from agrag.ingestion.vector_sync import VectorSync
from agrag.loaders.types import ErrorPolicy
from agrag.observability import record_stage_failure


def _embedding_record(
    entity: ResolvedEntity,
    vector: list[float],
    pending_job_id: str | None,
) -> dict[str, object]:
    """Build the optimistic graph embedding record for one resolved entity."""
    description = entity.properties.get("description")
    return {
        "id": str(entity.id),
        "vector": vector,
        "expected_name": entity.name,
        "expected_description": str(description) if description is not None else "",
        "pending_job_id": pending_job_id,
    }


def _embedding_guard_fields(entity: ResolvedEntity) -> dict[str, str]:
    """Return the current name and description required for a guarded write."""
    description = entity.properties.get("description")
    return {
        "expected_name": entity.name,
        "expected_description": str(description) if description else "",
    }


def _applied_ids(rows: list[dict[str, object]]) -> set[UUID]:
    """Return the node ids a guarded write in agrag.cypher.entities applied now.

    A row with ``written`` false belongs to a committed node that a job may not
    change yet. Its write is deferred to the commit, so it is neither applied
    nor a failure here. A record missing from the rows was skipped by the
    write's optimistic-concurrency guard.
    """
    return {
        UUID(str(row["id"]))
        for row in rows
        if isinstance(row, dict) and row.get("id") and row.get("written") is True
    }


async def _set_sync_status(
    entities: list[ResolvedEntity],
    *,
    graph_store: GraphStore,
    status: Literal["pending", "synced", "failed"],
    error: str | None = None,
) -> None:
    """Persist a resolved-vector synchronization state after graph rebuild."""
    await graph_store.execute_write(
        set_resolved_entity_sync_status_query(),
        {
            "records": [
                {"id": str(entity.id), "status": status, "error": error}
                for entity in entities
            ]
        },
    )
    for entity in entities:
        entity.vector_sync_status = status
        entity.vector_sync_error = error


async def embed_resolved_entities(
    entities: list[ResolvedEntity],
    *,
    embedder: Embedder,
    graph_store: GraphStore,
    error_policy: ErrorPolicy,
    pending_job_id: UUID | str | None = None,
    deferred: DeferredWrites | None = None,
    vector_sync: VectorSync | None = None,
) -> list[StageFailure]:
    """Write resolved-entity embeddings to the graph and record their sync status.

    Graph-native failures clear the graph vector. External-store failures
    record ``failed`` for a later repair pass.

    Only entities whose guarded graph write actually matched a live node have
    their sync status updated. A
    concurrent rebuild can replace or delete a ResolvedEntity between
    this call reading it and writing its embedding; skipping the unmatched
    ones keeps this call from resurrecting a vector, or overwriting a status,
    that the concurrent call already owns. Under a job, an embedding over a
    committed node is deferred to the commit and is not written yet.

    Raises:
        ValueError: ``pending_job_id`` is set and ``deferred`` is None.
    """
    if pending_job_id is not None and deferred is None:
        raise ValueError("deferred is required when pending_job_id is set")
    if not entities:
        return []
    job_id = str(pending_job_id) if pending_job_id is not None else None
    before = (
        {(target.kind, target.id) for target in deferred.vector_targets}
        if deferred is not None
        else set()
    )
    try:
        if vector_sync is not None:
            written_ids = await vector_sync.upsert_owned(
                VectorKind.RESOLVED_ENTITY,
                [
                    (
                        entity.id,
                        [RESOLVED_ENTITY_LABEL],
                        entity.embedding_text,
                        _embedding_guard_fields(entity),
                    )
                    for entity in entities
                ],
                job_id=pending_job_id,
                deferred=deferred,
            )
            synced_entities = [
                entity for entity in entities if entity.id in written_ids
            ]
            if synced_entities:
                await _set_sync_status(
                    synced_entities, graph_store=graph_store, status="synced"
                )
            return []
        vectors = await embedder.embed([entity.embedding_text for entity in entities])
        records: list[dict[str, object]] = []
        for entity, vector in zip(entities, vectors, strict=True):
            entity.embedding = vector
            records.append(_embedding_record(entity, vector, job_id))
        rows = await write_or_defer(
            graph_store,
            set_embedding_query(
                "embedding", vector_value=graph_store.vector_value("record.vector")
            ),
            records,
            deferred=deferred,
        )
        applied_ids = _applied_ids(rows)
        synced_entities = [entity for entity in entities if entity.id in applied_ids]
        if synced_entities:
            await _set_sync_status(
                synced_entities, graph_store=graph_store, status="synced"
            )
    except Exception as exc:  # noqa: BLE001
        if vector_sync is not None:
            deferred_ids = (
                {(target.kind, target.id) for target in deferred.vector_targets}
                - before
                if deferred is not None
                else set()
            )
            failed_entities = [
                entity
                for entity in entities
                if (VectorKind.RESOLVED_ENTITY, entity.id) not in deferred_ids
            ]
            with contextlib.suppress(Exception):
                await _set_sync_status(
                    failed_entities,
                    graph_store=graph_store,
                    status="failed",
                    error=str(exc),
                )
            if error_policy is ErrorPolicy.RAISE:
                raise
            trace_id, span_id = record_stage_failure(exc)
            return [
                StageFailure(
                    item_id="resolved_entity_embeddings",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    trace_id=trace_id,
                    span_id=span_id,
                )
            ]
        for entity in entities:
            entity.embedding = None
        cleared_ids: set[UUID] = set()
        with contextlib.suppress(Exception):
            cleared_rows = await graph_store.execute_write(
                clear_property_query("embedding"),
                {
                    "records": [
                        _embedding_record(entity, [], job_id) for entity in entities
                    ]
                },
            )
            cleared_ids = _applied_ids(cleared_rows)
        cleared_entities = [entity for entity in entities if entity.id in cleared_ids]
        if cleared_entities:
            with contextlib.suppress(Exception):
                await _set_sync_status(
                    cleared_entities,
                    graph_store=graph_store,
                    status="failed",
                    error=str(exc),
                )
        if error_policy is ErrorPolicy.RAISE:
            raise
        trace_id, span_id = record_stage_failure(exc)
        return [
            StageFailure(
                item_id="resolved_entity_embeddings",
                error_type=type(exc).__name__,
                error_message=str(exc),
                trace_id=trace_id,
                span_id=span_id,
            )
        ]
    return []
