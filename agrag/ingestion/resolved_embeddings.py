"""Embedding and vector synchronization for materialized resolved entities."""

import contextlib
from typing import Literal
from uuid import UUID

from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.vector_record import VectorRecord
from agrag.cypher.entities import clear_property_query, set_embedding_query
from agrag.cypher.resolution_write import (
    clear_resolved_entity_vector_deletions_query,
    enqueue_resolved_entity_vector_deletions_query,
    fetch_resolved_entity_vector_deletions_query,
    set_resolved_entity_sync_status_query,
)
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
    resolved node the graph has already replaced. A delete that fails is
    persisted so a later synchronization pass retries it.

    A component recomputed from an unchanged member set reuses its prior
    deterministic id, so ``removed_entity_ids``, or an earlier pass's
    persisted retry queue, can hold an id that ``entities`` is about to
    republish in this same call. That id is dropped from the pending
    deletions, and its stale queue entry must be cleared before that id's
    entity is republished; if the clear fails, that entity is held back
    from this call's embedding pass instead, so its queue entry can never
    survive alongside a freshly republished vector for a later pass to
    wrongly delete.

    Consolidation can also batch a materialization that recreated a
    component under its prior id together with a later one, in the same
    call, that supersedes it with a bigger merged component. Both ids look
    "about to be republished" up front, but only the later one's node
    still exists, so the guarded embedding write matches nothing for the
    superseded one. That outcome, not mere presence in ``entities``, is
    what confirms an id is still current: any assumed-current id that does
    not come back ``synced`` goes back on the deletion queue instead of
    being left orphaned with no cleanup record.
    """
    failures: list[StageFailure] = []
    republished_ids = {str(entity.id) for entity in entities}
    pending = await _pending_vector_deletions(graph_store)
    pending.update(
        {
            str(entity_id): vector_collection
            for entity_id in dict.fromkeys(removed_entity_ids)
        }
    )
    assumed_current = {
        item_id: collection
        for item_id, collection in pending.items()
        if item_id in republished_ids
    }
    for item_id in assumed_current:
        del pending[item_id]
    uncleared_stale_ids: set[str] = set()
    if assumed_current:
        try:
            await _clear_vector_deletions(
                graph_store, list(assumed_current), suppress=False
            )
        except Exception as exc:  # noqa: BLE001
            uncleared_stale_ids = set(assumed_current)
            failures.append(
                StageFailure(
                    item_id="resolved_entity_vector_store",
                    error_type=type(exc).__name__,
                    error_message=f"{exc} ids={list(assumed_current)}",
                )
            )
            if error_policy is ErrorPolicy.RAISE:
                raise
    if vector_store is not None and pending:
        failures.extend(
            await _delete_pending_vectors(
                pending,
                graph_store=graph_store,
                vector_store=vector_store,
                error_policy=error_policy,
            )
        )
    entities_to_sync = (
        [entity for entity in entities if str(entity.id) not in uncleared_stale_ids]
        if uncleared_stale_ids
        else entities
    )
    failures.extend(
        await embed_resolved_entities(
            entities_to_sync,
            embedder=embedder,
            graph_store=graph_store,
            vector_store=vector_store,
            vector_collection=vector_collection,
            error_policy=error_policy,
        )
    )
    synced_ids = {
        str(entity.id)
        for entity in entities_to_sync
        if entity.vector_sync_status == "synced"
    }
    superseded = {
        item_id: collection
        for item_id, collection in assumed_current.items()
        if item_id not in uncleared_stale_ids and item_id not in synced_ids
    }
    if superseded and vector_store is not None:
        failures.extend(
            await _delete_pending_vectors(
                superseded,
                graph_store=graph_store,
                vector_store=vector_store,
                error_policy=error_policy,
            )
        )
    return failures


async def _delete_pending_vectors(
    pending: dict[str, str],
    *,
    graph_store: GraphStore,
    vector_store: VectorStore,
    error_policy: ErrorPolicy,
) -> list[StageFailure]:
    """Delete every queued vector id, persisting a retry on failure.

    Args:
        pending: Vector ids to delete, mapped to the collection each lives
            in.
        graph_store: The graph store the deletion queue is persisted in.
        vector_store: The store to delete the vectors from.
        error_policy: Whether a delete failure raises or is recorded.

    Raises:
        Exception: A delete failed and ``error_policy`` is
            ``ErrorPolicy.RAISE``.
    """
    failures: list[StageFailure] = []
    for collection in sorted(set(pending.values())):
        ids = [
            UUID(item_id)
            for item_id, item_collection in pending.items()
            if item_collection == collection
        ]
        try:
            await vector_store.delete(collection, ids)
        except Exception as exc:  # noqa: BLE001
            await _enqueue_vector_deletions(
                graph_store, ids, collection=collection, error=str(exc)
            )
            failures.append(
                StageFailure(
                    item_id="resolved_entity_vector_store",
                    error_type=type(exc).__name__,
                    error_message=f"{exc} ids={ids}",
                )
            )
            if error_policy is ErrorPolicy.RAISE:
                raise
        else:
            await _clear_vector_deletions(
                graph_store, [str(entity_id) for entity_id in ids]
            )
    return failures


async def _pending_vector_deletions(graph_store: GraphStore) -> dict[str, str]:
    """Return durable vector deletion ids grouped by collection."""
    try:
        rows = await graph_store.execute_read(
            fetch_resolved_entity_vector_deletions_query()
        )
        return {
            str(row["id"]): str(row["collection"])
            for row in rows
            if isinstance(row, dict) and row.get("id") and row.get("collection")
        }
    except Exception:  # noqa: BLE001
        return {}


async def _enqueue_vector_deletions(
    graph_store: GraphStore,
    ids: list[UUID],
    *,
    collection: str,
    error: str,
) -> None:
    """Persist failed vector deletions for a later synchronization pass."""
    with contextlib.suppress(Exception):
        await graph_store.execute_write(
            enqueue_resolved_entity_vector_deletions_query(),
            {
                "records": [
                    {"id": str(entity_id), "collection": collection, "error": error}
                    for entity_id in ids
                ]
            },
        )


async def _clear_vector_deletions(
    graph_store: GraphStore, ids: list[str], *, suppress: bool = True
) -> None:
    """Remove deletion records after the vector store confirms deletion.

    Args:
        graph_store: The graph store the deletion queue is persisted in.
        ids: The queued deletion record ids to remove.
        suppress: When True, a write failure is swallowed because the
            queued deletion still points at a vector no later pass has
            republished, so it is safe to retry. Set False when ``ids`` are
            about to be republished instead, since a swallowed failure
            there would leave a stale queue entry for a live vector.

    Raises:
        Exception: The graph write failed and ``suppress`` is False.
    """
    if not ids:
        return
    if suppress:
        with contextlib.suppress(Exception):
            await graph_store.execute_write(
                clear_resolved_entity_vector_deletions_query(), {"ids": ids}
            )
    else:
        await graph_store.execute_write(
            clear_resolved_entity_vector_deletions_query(), {"ids": ids}
        )
