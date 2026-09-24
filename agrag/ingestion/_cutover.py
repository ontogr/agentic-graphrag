"""Crash-safe runner wrapping add/update/delete_document mutations.

``Graph`` stays the orchestrator; the job state machine lives here, taking
every dependency explicitly rather than reaching into ``Graph``.
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal, TypeVar
from uuid import UUID, uuid4

from agrag.common.data_models.graph_record import PENDING_JOB_ID_PROPERTY
from agrag.common.data_models.vector_record import (
    PENDING_VECTOR_FLAG,
    VectorRecord,
)
from agrag.cypher.cutover_job_write import (
    acquire_lease_query,
    clear_pending_tag_query,
    commit_job_query,
    finish_cleaning_query,
    renew_lease_query,
    rollback_job_query,
    start_cleaning_query,
    steal_expired_lease_query,
)
from agrag.graphdb.base import GraphStore
from agrag.ingestion._document_lifecycle import close_open_part_of_edges
from agrag.ingestion.settings import CutoverJobSettings
from agrag.vectordb.base import VectorStore


class CutoverJobLeaseError(Exception):
    """Another live Cutover Job holds the document's lease."""


T = TypeVar("T")
S = TypeVar("S")


async def _acquire_lease(
    *,
    document_key: str,
    verb: Literal["add", "update", "delete_document"],
    affected_entity_ids: list[UUID],
    graph_store: GraphStore,
    settings: CutoverJobSettings,
) -> tuple[UUID, UUID]:
    """Acquire the lease for one document, stealing only a dead one's.

    Returns:
        The new job's id and its fencing token.

    Raises:
        CutoverJobLeaseError: Another live job holds this document's lease.
    """
    job_id = uuid4()
    affected = [str(entity_id) for entity_id in affected_entity_ids]
    now = datetime.now(UTC)
    token = uuid4()
    rows = await graph_store.execute_write(
        acquire_lease_query(),
        {
            "job_id": str(job_id),
            "document_key": document_key,
            "verb": verb,
            "lease_token": str(token),
            "lease_expires_at": (
                now + timedelta(seconds=settings.lease_ttl_seconds)
            ).isoformat(),
            "affected_entity_ids": affected,
            "created_at": now.isoformat(),
        },
    )
    existing_token = rows[0].get("lease_token") if rows else None
    if existing_token == str(token):
        return job_id, token
    token = uuid4()
    now = datetime.now(UTC)
    rows = await graph_store.execute_write(
        steal_expired_lease_query(),
        {
            "job_id": str(job_id),
            "document_key": document_key,
            "expected_lease_token": existing_token,
            "verb": verb,
            "lease_token": str(token),
            "lease_expires_at": (
                now + timedelta(seconds=settings.lease_ttl_seconds)
            ).isoformat(),
            "affected_entity_ids": affected,
            "created_at": now.isoformat(),
        },
    )
    if rows and rows[0].get("lease_token") == str(token):
        return job_id, token
    raise CutoverJobLeaseError(
        f"Another live job holds the lease for document {document_key!r}."
    )


async def _renew_periodically(
    *,
    graph_store: GraphStore,
    job_id: UUID,
    token: UUID,
    ttl_seconds: int,
) -> None:
    """Extend the job's lease every third of the TTL until cancelled.

    A failed renewal is retried on the next tick; the lease fence on the
    job's transitions reports a lease that was lost for good.
    """
    while True:
        await asyncio.sleep(ttl_seconds / 3)
        with contextlib.suppress(Exception):
            await graph_store.execute_write(
                renew_lease_query(),
                {
                    "job_id": str(job_id),
                    "lease_token": str(token),
                    "lease_expires_at": (
                        datetime.now(UTC) + timedelta(seconds=ttl_seconds)
                    ).isoformat(),
                },
            )


async def clear_pending_vectors(
    *,
    vector_store: VectorStore | None,
    collections: Sequence[str],
    job_id: UUID,
) -> None:
    """Flip one job's pending vector payloads to committed.

    Scrolls each collection for this job's tag and re-upserts those records
    with the pending flag cleared. Idempotent: re-running finds nothing
    still flagged and writes nothing.

    The scroll asks for pending records explicitly: the store's default
    filter excludes them, which is exactly the set this call has to read.

    Args:
        vector_store: The store to clear in, or None to do nothing.
        collections: The collections this job may have written to.
        job_id: The committed job whose vectors clear.
    """
    if vector_store is None:
        return
    for collection in collections:
        page_offset: str | None = None
        while True:
            records, page_offset = await vector_store.scroll(
                collection,
                limit=100,
                page_offset=page_offset,
                filters={
                    PENDING_VECTOR_FLAG: True,
                    PENDING_JOB_ID_PROPERTY: str(job_id),
                },
                with_vectors=True,
            )
            if not records:
                break
            await vector_store.upsert(
                collection,
                [
                    VectorRecord(
                        id=record.id,
                        vector=record.vector,
                        payload={**record.payload, PENDING_VECTOR_FLAG: False},
                    )
                    for record in records
                ],
            )
            if page_offset is None:
                break


async def delete_pending_vectors(
    *,
    vector_store: VectorStore | None,
    collections: Sequence[str],
    job_id: UUID,
) -> None:
    """Delete one job's pending vector payloads, for rollback.

    Scrolls each collection for this job's tag and deletes those records
    outright. Unlike :func:`clear_pending_vectors`, which flips a
    committed job's flag, a rolled-back job's writes were never
    committed, so nothing about them should survive.

    Args:
        vector_store: The store to delete from, or None to do nothing.
        collections: The collections this job may have written to.
        job_id: The rolled-back job whose vectors are deleted.
    """
    if vector_store is None:
        return
    for collection in collections:
        page_offset: str | None = None
        while True:
            records, page_offset = await vector_store.scroll(
                collection,
                limit=100,
                page_offset=page_offset,
                filters={
                    PENDING_VECTOR_FLAG: True,
                    PENDING_JOB_ID_PROPERTY: str(job_id),
                },
            )
            if not records:
                break
            await vector_store.delete(collection, [record.id for record in records])
            if page_offset is None:
                break


async def _rollback(
    *,
    graph_store: GraphStore,
    vector_store: VectorStore | None,
    vector_collections: Sequence[str],
    job_id: UUID,
) -> None:
    """Delete everything a job wrote, suppressing rollback's own errors."""
    with contextlib.suppress(Exception):
        await delete_pending_vectors(
            vector_store=vector_store, collections=vector_collections, job_id=job_id
        )
    with contextlib.suppress(Exception):
        await graph_store.execute_write(rollback_job_query(), {"job_id": str(job_id)})


async def run_cutover_job(
    *,
    verb: Literal["add", "update", "delete_document"],
    document_key: str,
    affected_entity_ids: list[UUID],
    graph_store: GraphStore,
    vector_store: VectorStore | None,
    vector_collections: Sequence[str],
    settings: CutoverJobSettings,
    pending_write: Callable[[UUID], Awaitable[T]],
    cleanup: Callable[[], Awaitable[S]],
    close_document_node_id: UUID | None = None,
) -> tuple[T, S, int]:
    """Run one crash-safe graph-mutating call end to end.

    Acquires the document's lease, runs ``pending_write`` with the new job
    id (every write it makes carries that id's pending tag), then flips
    the job to committed, closes the superseded version's PART_OF edges,
    and clears the tag in one transaction. After that the cleanup phase
    runs against the snapshot: a crash before commit rolls back on the
    next open, a crash after rolls forward, so the graph always converges
    to as-if-never-happened or as-if-completed.

    Args:
        verb: Which public method created this job.
        document_key: The document this job mutates, lease-guarded.
        affected_entity_ids: Entities with evidence in the version being
            replaced or removed, snapshotted before any pending write.
            Empty for add. Only these may be pruned by cleanup.
        graph_store: Where the job node and all writes live.
        vector_store: Second write target for embeddings, if configured.
        vector_collections: Collections the pending phase may have
            written pending-tagged vectors to.
        settings: Lease TTL configuration. The lease is renewed every third
            of the TTL while the job runs, so a phase can outlast the TTL.
        pending_write: The caller's pipeline stages, tagging every write
            with the passed job id.
        cleanup: Post-commit work over the snapshot (closing is already
            done; typically deletion-triggered pruning).
        close_document_node_id: The persisted Document node whose open
            PART_OF edges close atomically with the commit. None closes
            nothing, for add.

    Returns:
        The pending-write result, the cleanup result, and the number of
        PART_OF edges closed by the commit.

    Raises:
        CutoverJobLeaseError: Another live job holds the lease, or this
            job lost its lease before a fenced transition.
        Exception: Whatever ``pending_write`` or ``cleanup`` raised, after
            rolling back (pre-commit) or leaving the job for resume
            (post-commit).
    """
    job_id, token = await _acquire_lease(
        document_key=document_key,
        verb=verb,
        affected_entity_ids=affected_entity_ids,
        graph_store=graph_store,
        settings=settings,
    )
    renewal = asyncio.create_task(
        _renew_periodically(
            graph_store=graph_store,
            job_id=job_id,
            token=token,
            ttl_seconds=settings.lease_ttl_seconds,
        )
    )
    try:
        return await _run_leased(
            job_id=job_id,
            token=token,
            graph_store=graph_store,
            vector_store=vector_store,
            vector_collections=vector_collections,
            pending_write=pending_write,
            cleanup=cleanup,
            close_document_node_id=close_document_node_id,
        )
    finally:
        renewal.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await renewal


async def _run_leased(
    *,
    job_id: UUID,
    token: UUID,
    graph_store: GraphStore,
    vector_store: VectorStore | None,
    vector_collections: Sequence[str],
    pending_write: Callable[[UUID], Awaitable[T]],
    cleanup: Callable[[], Awaitable[S]],
    close_document_node_id: UUID | None,
) -> tuple[T, S, int]:
    """Run the pending, commit, and cleanup phases under a held lease."""
    job_arg = str(job_id)
    token_arg = str(token)
    try:
        pending_result = await pending_write(job_id)
    except Exception:
        await _rollback(
            graph_store=graph_store,
            vector_store=vector_store,
            vector_collections=vector_collections,
            job_id=job_id,
        )
        raise
    try:
        async with graph_store.transaction() as txn:
            committed = await txn.execute_write(
                commit_job_query(),
                {"job_id": job_arg, "lease_token": token_arg},
            )
            if not committed:
                raise CutoverJobLeaseError(
                    f"Job {job_arg} lost its lease before commit."
                )
            # The close runs before the tag clear so it can tell the
            # superseded version's edges from the ones this job just
            # wrote; both land in the same transaction as the flip.
            chunks_closed = 0
            if close_document_node_id is not None:
                chunks_closed = await close_open_part_of_edges(
                    txn,
                    document_node_id=close_document_node_id,
                    job_id=job_id,
                )
            await txn.execute_write(clear_pending_tag_query(), {"job_id": job_arg})
    except Exception:
        await _rollback(
            graph_store=graph_store,
            vector_store=vector_store,
            vector_collections=vector_collections,
            job_id=job_id,
        )
        raise
    started = await graph_store.execute_write(
        start_cleaning_query(), {"job_id": job_arg, "lease_token": token_arg}
    )
    if not started:
        raise CutoverJobLeaseError(f"Job {job_arg} lost its lease before cleanup.")
    cleanup_result = await cleanup()
    await clear_pending_vectors(
        vector_store=vector_store, collections=vector_collections, job_id=job_id
    )
    finished = await graph_store.execute_write(
        finish_cleaning_query(), {"job_id": job_arg, "lease_token": token_arg}
    )
    if not finished:
        raise CutoverJobLeaseError(f"Job {job_arg} lost its lease after cleanup.")
    return pending_result, cleanup_result, chunks_closed
