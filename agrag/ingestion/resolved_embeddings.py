"""Embedding and vector synchronization for materialized resolved entities."""

import contextlib
from typing import Literal
from uuid import UUID

from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.vector_record import VectorRecord
from agrag.cypher.entities import clear_property_query, set_embedding_query
from agrag.cypher.resolution_write import set_resolved_entity_sync_status_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion.stats import StageFailure
from agrag.loaders.corpus.types import ErrorPolicy
from agrag.vectordb.base import VectorStore


def _embedding_record(entity: ResolvedEntity, vector: list[float]) -> dict[str, object]:
    """Build the optimistic graph embedding record for one resolved entity."""
    description = entity.properties.get("description")
    return {
        "id": str(entity.id),
        "vector": vector,
        "expected_name": entity.name,
        "expected_description": str(description) if description is not None else "",
    }


def _matched_ids(rows: list[dict[str, object]]) -> set[UUID]:
    """Return the node ids a guarded write in agrag.cypher.entities matched.

    A row is missing for any record the write's optimistic-concurrency guard
    skipped, because a concurrent write already changed or removed that node.
    """
    return {
        UUID(str(row["id"])) for row in rows if isinstance(row, dict) and row.get("id")
    }


async def _set_sync_status(
    entities: list[ResolvedEntity],
    *,
    graph_store: GraphStore,
    status: Literal["pending", "synced", "failed"],
    error: str | None = None,
) -> None:
    """Persist a resolved-vector synchronization state after graph materialization."""
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
    vector_store: VectorStore | None,
    vector_collection: str,
    error_policy: ErrorPolicy,
) -> list[StageFailure]:
    """Write resolved-entity embeddings to the graph and optional vector store.

    Graph writes finish before vector-store synchronization because the two
    stores cannot share a transaction. A failed sync clears the graph vector,
    removes any old mirrored vector, and records ``failed`` for a later
    materialization pass to retry.

    Only entities whose guarded graph write actually matched a live node are
    mirrored to the vector store or have their sync status updated. A
    concurrent materialization can replace or delete a ResolvedEntity between
    this call reading it and writing its embedding; skipping the unmatched
    ones keeps this call from resurrecting a vector, or overwriting a status,
    that the concurrent call already owns.
    """
    if not entities:
        return []
    try:
        vectors = await embedder.embed([entity.embedding_text for entity in entities])
        records: list[dict[str, object]] = []
        vector_records_by_id: dict[UUID, VectorRecord] = {}
        for entity, vector in zip(entities, vectors, strict=True):
            entity.embedding = vector
            records.append(_embedding_record(entity, vector))
            vector_records_by_id[entity.id] = VectorRecord(
                id=entity.id,
                vector=vector,
                payload={
                    "label": entity.label,
                    "name": entity.name,
                    "text": entity.embedding_text,
                    "member_ids": [str(member_id) for member_id in entity.member_ids],
                    "resolved": True,
                    **entity.properties,
                },
            )
        rows = await graph_store.execute_write(
            set_embedding_query("embedding"), {"records": records}
        )
        matched_ids = _matched_ids(rows)
        synced_entities = [entity for entity in entities if entity.id in matched_ids]
        if vector_store is not None and synced_entities:
            await vector_store.upsert(
                vector_collection,
                [vector_records_by_id[entity.id] for entity in synced_entities],
            )
        if synced_entities:
            await _set_sync_status(
                synced_entities, graph_store=graph_store, status="synced"
            )
    except Exception as exc:  # noqa: BLE001
        for entity in entities:
            entity.embedding = None
        cleared_ids: set[UUID] = set()
        with contextlib.suppress(Exception):
            cleared_rows = await graph_store.execute_write(
                clear_property_query("embedding"),
                {"records": [_embedding_record(entity, []) for entity in entities]},
            )
            cleared_ids = _matched_ids(cleared_rows)
        cleared_entities = [entity for entity in entities if entity.id in cleared_ids]
        if vector_store is not None and cleared_entities:
            with contextlib.suppress(Exception):
                await vector_store.delete(
                    vector_collection, [entity.id for entity in cleared_entities]
                )
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
        return [
            StageFailure(
                item_id="resolved_entity_embeddings",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        ]
    return []


async def _synchronize_resolved_entity_vectors(
    entities: list[ResolvedEntity],
    removed_entity_ids: list[UUID],
    *,
    embedder: Embedder,
    graph_store: GraphStore,
    vector_store: VectorStore | None,
    vector_collection: str,
    error_policy: ErrorPolicy,
) -> list[StageFailure]:
    """Replace stale resolved vectors and synchronize current materializations.

    The stale-vector delete runs before a later graph write can fail after
    materialization. This keeps an external vector store from serving a
    resolved node the graph has already replaced.
    """
    failures: list[StageFailure] = []
    if removed_entity_ids and vector_store is not None:
        try:
            await vector_store.delete(
                vector_collection, list(dict.fromkeys(removed_entity_ids))
            )
        except Exception as exc:  # noqa: BLE001
            if error_policy is ErrorPolicy.RAISE:
                raise
            # ponytail: ids are lost on retry without a persistent
            # pending-deletion queue; surfacing them here is a stopgap for
            # manual follow-up until that queue exists.
            failures.append(
                StageFailure(
                    item_id="resolved_entity_vector_store",
                    error_type=type(exc).__name__,
                    error_message=f"{exc} ids={removed_entity_ids}",
                )
            )
    failures.extend(
        await embed_resolved_entities(
            entities,
            embedder=embedder,
            graph_store=graph_store,
            vector_store=vector_store,
            vector_collection=vector_collection,
            error_policy=error_policy,
        )
    )
    return failures
