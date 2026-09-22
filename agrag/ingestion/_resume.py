"""Crash recovery for interrupted Cutover Jobs, run from ``Graph.open()``.

The resume hook closes the loop the Cutover Job runner leaves open when a
process dies mid-call. A job whose worker died before its commit flip is
rolled back — its tagged writes are deleted, and the live graph never saw
them. A job that died after committing is rolled forward: its cleanup
phase runs against the snapshot the job recorded, its pending vector
payloads flip to committed, and the job reaches its terminal state. Every
outcome converges to as-if-never-happened or as-if-completed.

A pending job whose lease is still live is skipped: its worker may be
running normally in another process, and only a lapsed lease means the
document was abandoned.
"""

import contextlib
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from agrag.common.data_models.cutover_job import CutoverJobStatus
from agrag.cypher.cutover_job_read import find_incomplete_jobs_query
from agrag.cypher.cutover_job_write import (
    claim_job_query,
    finish_cleaning_query,
    rollback_job_query,
)
from agrag.graphdb.base import GraphStore
from agrag.ingestion._cutover import clear_pending_vectors, delete_pending_vectors
from agrag.ingestion.settings import CutoverJobSettings


async def resume_incomplete_jobs(
    graph_store: GraphStore,
    *,
    vector_store: Any = None,
    vector_collections: Sequence[str] = (),
    roll_forward: Callable[[list[UUID]], Awaitable[None]] | None = None,
    lease_ttl_seconds: int = CutoverJobSettings().lease_ttl_seconds,
) -> list[str]:
    """Recover every incomplete Cutover Job found in the graph.

    Args:
        graph_store: The store just connected and provisioned.
        vector_store: The optional second write target; a rolled-back
            job's pending vectors are deleted from it, a rolled-forward
            job's are flipped to committed.
        vector_collections: The collections the pending phase may have
            written to.
        roll_forward: Runs one rolled-forward job's cleanup over its
            affected-entity snapshot. None rolls forward without pruning,
            which leaves the snapshot on the job node for a later caller.
        lease_ttl_seconds: Lease duration for a resume claimant.

    Returns:
        The recovered job ids, in the order handled. Each was either
        rolled back (deleted with its writes) or rolled forward (its
        cleanup finished and the job marked done). A job skipped because a
        live lease still holds it, or claimed by a concurrent open, is not
        reported.
    """
    try:
        job_rows = await graph_store.execute_read(find_incomplete_jobs_query())
    except Exception:  # noqa: BLE001
        # A graph that predates this feature, or a store whose read
        # failed, must not break opening the graph.
        return []
    handled: list[str] = []
    for row in job_rows:
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        job_id = str(row["id"])
        status = str(row.get("status") or "")
        if status == CutoverJobStatus.PENDING:
            if not row.get("lease_expired"):
                continue
            if await _roll_back(
                graph_store,
                job_id=job_id,
                vector_store=vector_store,
                vector_collections=vector_collections,
            ):
                handled.append(job_id)
            continue
        if row.get("lease_token") is None:
            continue
        if not row.get("lease_expired"):
            continue
        if await _roll_forward(
            graph_store,
            job_id=job_id,
            affected_entity_ids=_affected_entity_ids(row),
            vector_store=vector_store,
            vector_collections=vector_collections,
            prune=roll_forward,
            lease_token=str(row["lease_token"]),
            lease_ttl_seconds=lease_ttl_seconds,
        ):
            handled.append(job_id)
    return handled


def _affected_entity_ids(row: dict[str, Any]) -> list[UUID]:
    """Return one job's recorded affected-entity snapshot as ids.

    Returns:
        The snapshot's ids, skipping any entry that is not a UUID.
    """
    raw = row.get("affected_entity_ids") or []
    if not isinstance(raw, list):
        return []
    ids: list[UUID] = []
    for value in raw:
        try:
            ids.append(UUID(str(value)))
        except ValueError:
            continue
    return ids


async def _roll_back(
    graph_store: GraphStore,
    *,
    job_id: str,
    vector_store: Any,
    vector_collections: Sequence[str],
) -> bool:
    """Delete one abandoned pending job's writes and the job node itself.

    The job's worker died without committing, so nothing it wrote was ever
    visible; deleting the tagged rows and pending vectors restores the
    graph to its pre-call state.

    Returns:
        Whether the deletion ran without raising.
    """
    try:
        await delete_pending_vectors(
            vector_store=vector_store,
            collections=vector_collections,
            job_id=UUID(job_id),
        )
        await graph_store.execute_write(rollback_job_query(), {"job_id": job_id})
    except Exception:  # noqa: BLE001
        return False
    return True


async def _roll_forward(
    graph_store: GraphStore,
    *,
    job_id: str,
    affected_entity_ids: list[UUID],
    vector_store: Any,
    vector_collections: Sequence[str],
    prune: Callable[[list[UUID]], Awaitable[None]] | None,
    lease_token: str,
    lease_ttl_seconds: int,
) -> bool:
    """Finish one committed-or-cleaning job's remaining cleanup work.

    The commit cleared the job's pending tags atomically, so what is left
    is the cleanup phase the crashed worker never reached: pruning the
    job's snapshot, flipping the vector payloads still flagged pending,
    and the terminal ``done`` flip. All three are idempotent, so a resume
    that dies part way through simply re-runs them on the next open.

    A prune that raises leaves the job in ``cleaning`` — terminal only
    once its cleanup actually completed — so a later open retries it.

    Returns:
        Whether this open claimed the job. Another open that claimed it
        first, or a claim that could not be written, reports ``False``.
    """
    token = str(uuid4())
    expires_at = datetime.now(UTC) + timedelta(seconds=lease_ttl_seconds)
    try:
        claimed = await graph_store.execute_write(
            claim_job_query(),
            {
                "job_id": job_id,
                "expected_lease_token": lease_token,
                "lease_token": token,
                "lease_expires_at": expires_at.isoformat(),
            },
        )
    except Exception:  # noqa: BLE001
        return False
    if not claimed:
        return False
    pruned = prune is not None or not affected_entity_ids
    if prune is not None and affected_entity_ids:
        try:
            await prune(affected_entity_ids)
        except Exception:  # noqa: BLE001
            pruned = False
    vectors_cleared = True
    try:
        await clear_pending_vectors(
            vector_store=vector_store,
            collections=vector_collections,
            job_id=UUID(job_id),
        )
    except Exception:  # noqa: BLE001
        vectors_cleared = False
    if pruned and vectors_cleared:
        with contextlib.suppress(Exception):
            await graph_store.execute_write(
                finish_cleaning_query(), {"job_id": job_id, "lease_token": token}
            )
    return True
