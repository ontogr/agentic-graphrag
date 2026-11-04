"""Crash-safe runner wrapping add/update/delete_document mutations.

``Graph`` stays the orchestrator; the job state machine lives here, taking
every dependency explicitly rather than reaching into ``Graph``.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, TypeVar
from uuid import NAMESPACE_OID, UUID, uuid4, uuid5

from opentelemetry.trace import Tracer
from pydantic import TypeAdapter

from agrag.common.data_models.graph_record import DeferredWrites
from agrag.common.data_models.stage_failure import StageFailure
from agrag.common.data_models.vector_record import (
    VectorKind,
    VectorTarget,
    VectorWork,
)
from agrag.cypher.candidates import (
    delete_reviewed_job_candidates_query,
    delete_stale_candidates_query,
)
from agrag.cypher.cutover_job_write import (
    acquire_lease_query,
    begin_commit_query,
    begin_rollback_query,
    claim_pending_job_query,
    commit_job_query,
    finish_cleaning_query,
    job_status_query,
    record_parts_closed_query,
    renew_lease_query,
    resume_commit_fence_query,
    start_cleaning_query,
    steal_terminal_job_query,
)
from agrag.cypher.documents import (
    flag_decisions_for_activation_query,
    purge_candidate_evidence_query,
    purge_document_nodes_query,
    purge_relation_evidence_query,
    record_activation_query,
    retire_document_version_query,
    set_chunk_extraction_fingerprint_query,
)
from agrag.cypher.relations import (
    delete_document_mentions_query,
    retract_document_relation_evidence_query,
)
from agrag.cypher.vector_cleanup import document_chunk_ids_query
from agrag.graphdb.base import GraphStore, GraphStoreTransaction
from agrag.graphdb.errors import (
    GraphStoreConstraintViolationError,
    GraphStoreWriteConflictError,
)
from agrag.ingestion._deferred import replay_deferred
from agrag.ingestion._document_lifecycle import (
    DocumentChange,
    close_open_has_part_edges,
)
from agrag.ingestion._pending_rows import (
    clear_job_tags,
    fold_job_relations,
    rollback_job_rows,
)
from agrag.ingestion.resolved_entities import MatchComponent
from agrag.ingestion.settings import CutoverJobSettings
from agrag.ingestion.vector_sync import VectorSync
from agrag.observability import get_tracer


class CutoverJobLeaseError(Exception):
    """Another live Cutover Job holds the document's lease."""


@dataclass(frozen=True, slots=True)
class InPlaceRefresh:
    """What the commit transaction changes for a re-extract that keeps its chunks.

    The commit removes the old entity mentions and evidence of the refreshed
    chunks, then stamps them with the new extraction fingerprint. Chunks that
    were left out of ``chunk_ids`` because their extraction failed keep their
    evidence and their stamps.

    Attributes:
        document_node_id: The id of the Document node that owns the chunks.
        chunk_ids: The open chunks whose old evidence the commit replaces.
        extraction_fingerprint: The stamp for ``chunk_ids``, or ``None`` when
            the commit must leave the stamps as they are.
    """

    document_node_id: UUID
    chunk_ids: Sequence[UUID]
    extraction_fingerprint: str | None


T = TypeVar("T")
S = TypeVar("S")

_COMMIT_RETRY_INITIAL_DELAY_SECONDS = 0.1
_COMMIT_RETRY_MAX_DELAY_SECONDS = 2.0


def lease_expiry_millis(expires_at: datetime) -> int:
    """Return a lease expiry as epoch milliseconds, the form the lease Cypher stores.

    The Cypher compares the stored value with ``timestamp()``, which is also
    epoch milliseconds, so both sides use the same clock and unit.
    """
    return int(expires_at.timestamp() * 1000)


async def _acquire_lease(
    *,
    document_key: str,
    verb: Literal["add", "update", "delete_document", "purge_document"],
    affected_entity_ids: list[UUID],
    graph_store: GraphStore,
    settings: CutoverJobSettings,
    vector_sync: VectorSync | None,
) -> tuple[UUID, UUID]:
    """Acquire the lease for one document, rolling back a dead run first.

    An expired pending or rolling-back job still owns tagged rows, so it is
    rolled back before the document is taken over.
    A finished job (done or rolled_back) is taken over in place.

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
            "lease_expires_at": lease_expiry_millis(
                now + timedelta(seconds=settings.lease_ttl_seconds)
            ),
            "affected_entity_ids": affected,
            "created_at": now.isoformat(),
        },
    )
    existing_token = rows[0].get("lease_token") if rows else None
    if existing_token == str(token):
        return job_id, token
    if (
        rows
        and rows[0].get("status") in ("pending", "rolling_back")
        and rows[0].get("lease_expired")
    ):
        rollback_token = uuid4()
        now = datetime.now(UTC)
        claimed = await graph_store.execute_write(
            claim_pending_job_query(),
            {
                "job_id": str(rows[0]["id"]),
                "expected_lease_token": existing_token,
                "lease_token": str(rollback_token),
                "lease_expires_at": lease_expiry_millis(
                    now + timedelta(seconds=settings.lease_ttl_seconds)
                ),
            },
        )
        if claimed:
            rollback_job_id = UUID(str(rows[0]["id"]))
            rolled_back = await rollback_job_rows(
                graph_store,
                job_id=rollback_job_id,
                token=rollback_token,
                vector_sync=vector_sync,
            )
            if rolled_back:
                return await _acquire_lease(
                    document_key=document_key,
                    verb=verb,
                    affected_entity_ids=affected_entity_ids,
                    graph_store=graph_store,
                    settings=settings,
                    vector_sync=vector_sync,
                )
    token = uuid4()
    now = datetime.now(UTC)
    rows = await graph_store.execute_write(
        steal_terminal_job_query(),
        {
            "job_id": str(job_id),
            "document_key": document_key,
            "expected_lease_token": existing_token,
            "verb": verb,
            "lease_token": str(token),
            "lease_expires_at": lease_expiry_millis(
                now + timedelta(seconds=settings.lease_ttl_seconds)
            ),
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
    stop_event: asyncio.Event,
    stopped_event: asyncio.Event,
) -> None:
    """Extend the job's lease every third of the TTL until finalization.

    Raises:
        CutoverJobLeaseError: The job no longer holds its lease.
    """
    try:
        while True:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=ttl_seconds / 3)
            except TimeoutError:
                pass
            else:
                return
            renewed = await graph_store.execute_write(
                renew_lease_query(),
                {
                    "job_id": str(job_id),
                    "lease_token": str(token),
                    "lease_expires_at": lease_expiry_millis(
                        datetime.now(UTC) + timedelta(seconds=ttl_seconds)
                    ),
                },
            )
            if not renewed:
                raise CutoverJobLeaseError(
                    f"Job {job_id} lost its lease during renewal."
                )
    finally:
        stopped_event.set()


async def _rollback(
    *,
    graph_store: GraphStore,
    job_id: UUID,
    token: UUID,
    vector_sync: VectorSync | None,
) -> bool:
    """Delete pending writes only after a token-fenced rollback transition.

    A successful graph rollback is followed by removal of vectors whose nodes
    the rollback deleted.

    Returns:
        Whether the job entered rollback and its graph rows were deleted.
    """
    job_arg = str(job_id)
    token_arg = str(token)
    try:
        begun = await graph_store.execute_write(
            begin_rollback_query(), {"job_id": job_arg, "lease_token": token_arg}
        )
    except Exception:  # noqa: BLE001
        return False
    if not begun:
        return False
    try:
        return await rollback_job_rows(
            graph_store, job_id=job_id, token=token, vector_sync=vector_sync
        )
    except Exception:  # noqa: BLE001
        return False


async def _read_job_row(graph_store: GraphStore, *, job_id: UUID) -> dict[str, Any]:
    """Read one job's status row through the write-routed database path.

    The write path sees the effects of a failed attempt that a replica
    could still miss. Returns an empty dict when the job node is absent.
    """
    rows = await graph_store.execute_write(job_status_query(), {"job_id": str(job_id)})
    return rows[0] if rows else {}


def _applied_parts_closed(row: Mapping[str, Any], token: UUID) -> int | None:
    """Return the recorded closed-edge count when a job row shows the commit applied.

    The commit is applied when recovery moved the job to cleaning or done, or
    when this token committed it. None means the commit is not applied.
    """
    if row.get("status") in {"cleaning", "done"}:
        return int(row.get("parts_closed") or 0)
    if row.get("status") == "committed" and row.get("lease_token") == str(token):
        return int(row.get("parts_closed") or 0)
    return None


async def _commit_applied(
    *, graph_store: GraphStore, job_id: UUID, token: UUID
) -> int | None:
    """Return the recorded closed-edge count when the commit is applied.

    Returns:
        The recorded parts-closed count when this token committed the job
        or recovery has advanced it to cleaning or done. None when the job
        is absent, uncommitted, or still committed under another token.
    """
    row = await _read_job_row(graph_store, job_id=job_id)
    return _applied_parts_closed(row, token)


async def _settle_failed_commit(
    *,
    graph_store: GraphStore,
    job_id: UUID,
    token: UUID,
    vector_sync: VectorSync | None,
) -> int | None:
    """Keep committed work or safely roll back a failed pending commit.

    An unreadable status is left for recovery; no graph rows are deleted
    because the commit outcome is unknown.
    """
    try:
        applied = await _commit_applied(
            graph_store=graph_store, job_id=job_id, token=token
        )
    except Exception:  # noqa: BLE001
        return None
    if applied is not None:
        return applied
    await _rollback(
        graph_store=graph_store,
        job_id=job_id,
        token=token,
        vector_sync=vector_sync,
    )
    return None


def _component_seed_ids(components: Sequence[MatchComponent]) -> list[UUID]:
    """Return one member id for each component, the lowest by string order."""
    return [
        min((member.id for member in members), key=str)
        for _, members in components
        if members
    ]


async def _purge_document_content(
    txn: GraphStoreTransaction, *, document_node_id: UUID
) -> None:
    """Hard-delete every version's content of one document inside the commit.

    The relation evidence is stripped first, while the chunk ids it cites are
    still on the chunks. Pending candidates that cite the chunks go next, then
    the chunk, section, table and figure nodes.
    """
    params = {"document_node_id": str(document_node_id)}
    await txn.execute_write(purge_relation_evidence_query(), params)
    await txn.execute_write(purge_candidate_evidence_query(), params)
    await txn.execute_write(purge_document_nodes_query(), params)


def _activation_params(job_id: UUID, change: DocumentChange) -> dict[str, object]:
    """Return the parameters of the activation record one job writes.

    The record id depends only on the job id, so a retried commit names the
    same record.
    """
    return {
        "document_node_id": str(change.document_node_id),
        "id": str(uuid5(NAMESPACE_OID, f"DocumentActivation:{job_id}")),
        "document_key": change.document_key,
        "verb": change.verb,
        "content_hash": change.content_hash,
        "previous_content_hash": change.previous_content_hash,
        "version_id": change.version_id,
        "job_id": str(job_id),
        "activated_at": datetime.now(UTC).isoformat(),
    }


@dataclass(frozen=True, slots=True)
class CommitPlan:
    """The document-level writes of one commit, kept on the job for recovery.

    The commit stores the plan with its start mark. A backend without
    multi-statement transactions can lose the worker part way through, and
    recovery replays the steps that had not finished from the stored plan. The
    plan holds the deferred writes too, so recovery replays them in the same
    place as the commit does, between the retraction and the fold.

    Attributes:
        close_document_node_id: The document whose open edges the commit closes.
        candidate_document_node_id: The document whose stale candidates the
            commit replaces.
        keep_node_ids: The nodes whose edges the close leaves open.
        in_place: The in-place refresh, when the commit keeps its chunks.
        change: The document change recorded as an activation, if any.
        deferred: The deferred writes of the commit as ``(query, parameters)``
            pairs in write order. Their parameters hold only JSON-safe values,
            because the graph store converts ids to strings before a write is
            deferred.
        vector_targets: Committed graph nodes to sync after the commit.
        vector_deletes: Vectors whose graph nodes the commit deletes.
    """

    close_document_node_id: UUID | None
    candidate_document_node_id: UUID | None
    keep_node_ids: list[UUID]
    in_place: InPlaceRefresh | None
    change: DocumentChange | None
    deferred: list[tuple[str, dict[str, Any]]]
    vector_targets: list[VectorTarget] = field(default_factory=list)
    vector_deletes: list[VectorTarget] = field(default_factory=list)


_PLAN_ADAPTER = TypeAdapter(CommitPlan)


def parse_commit_plan(raw: str) -> CommitPlan:
    """Return the plan a job stored when its commit started."""
    return _PLAN_ADAPTER.validate_json(raw)


async def apply_plan_before_replay(
    txn: GraphStoreTransaction, plan: CommitPlan
) -> None:
    """Retract the committed evidence an in-place refresh replaces.

    Every statement is safe to repeat.
    """
    if plan.in_place is None:
        return
    refresh_params = {
        "document_node_id": str(plan.in_place.document_node_id),
        "chunk_ids": [str(chunk_id) for chunk_id in plan.in_place.chunk_ids],
    }
    await txn.execute_write(retract_document_relation_evidence_query(), refresh_params)
    await txn.execute_write(delete_document_mentions_query(), refresh_params)


async def apply_plan_after_fold(
    txn: GraphStoreTransaction, *, job_id: UUID, plan: CommitPlan
) -> int:
    """Run the document writes that follow the fold and mark them applied.

    Every statement is safe to repeat while the job's rows are still tagged,
    which is the case until the commit clears them. The closing mark is the
    last statement, so a job with the mark has applied all of them.

    Returns:
        The number of document edges closed.
    """
    if plan.in_place is not None and plan.in_place.extraction_fingerprint is not None:
        await txn.execute_write(
            set_chunk_extraction_fingerprint_query(),
            {
                "chunk_ids": [str(chunk_id) for chunk_id in plan.in_place.chunk_ids],
                "extraction_fingerprint": plan.in_place.extraction_fingerprint,
            },
        )
    parts_closed = 0
    if plan.close_document_node_id is not None:
        parts_closed = await close_open_has_part_edges(
            txn,
            document_node_id=plan.close_document_node_id,
            job_id=job_id,
            keep_node_ids=plan.keep_node_ids,
        )
    if plan.candidate_document_node_id is not None:
        # A review can settle a key after extraction's early lookup.
        # Recheck while the new candidates are still invisible to readers.
        await txn.execute_write(
            delete_reviewed_job_candidates_query(), {"job_id": str(job_id)}
        )
        await txn.execute_write(
            delete_stale_candidates_query(),
            {"document_node_id": str(plan.candidate_document_node_id)},
        )
    change = plan.change
    if change is not None and change.verb == "purge":
        await _purge_document_content(txn, document_node_id=change.document_node_id)
    if change is not None:
        activation_params = _activation_params(job_id, change)
        await txn.execute_write(record_activation_query(), activation_params)
        await txn.execute_write(
            flag_decisions_for_activation_query(),
            {"activation_id": activation_params["id"]},
        )
        if change.verb == "delete":
            await txn.execute_write(
                retire_document_version_query(),
                {"document_node_id": str(change.document_node_id)},
            )
    await txn.execute_write(record_parts_closed_query(), {"job_id": str(job_id)})
    return parts_closed


async def apply_commit_steps(
    txn: GraphStoreTransaction,
    *,
    plan: CommitPlan | None,
    job_id: UUID,
    token: UUID,
    skip: int,
    docs_applied: bool,
    component_seed_ids: Sequence[UUID],
    created_entity_ids: Sequence[UUID],
) -> int:
    """Run the commit steps that have not run yet, then flip the job to committed.

    The live commit and crash recovery both call this, so the step order is
    defined once. The retraction runs only with the first replay step. Running
    it again after a replay step had already written evidence would delete
    that evidence.

    Args:
        txn: The transaction the steps run in.
        plan: The stored commit plan, or None for a commit with no document
            writes. Its deferred writes are the replay steps.
        job_id: The job to commit.
        token: The lease token the caller holds.
        skip: How many deferred steps already ran.
        docs_applied: Whether the closing document writes already ran.
        component_seed_ids: Components the cleanup rebuilds.
        created_entity_ids: Entities the cleanup reconciles.

    Returns:
        The number of HAS_PART edges closed by the closing writes, or 0 when
        they ran in an earlier attempt.

    Raises:
        CutoverJobLeaseError: The flip found the lease lost.
    """
    if plan is not None and not docs_applied:
        if skip == 0:
            # The retraction must precede the replay, which writes back the
            # relations the new run finds again. It reads the MENTIONED_IN
            # edges, so it runs before the replay can recreate them.
            await apply_plan_before_replay(txn, plan)
        await replay_deferred(
            txn,
            DeferredWrites(entries=list(plan.deferred)),
            job_id=job_id,
            skip=skip,
        )
    await fold_job_relations(txn, job_id=job_id)
    parts_closed = 0
    if plan is not None and not docs_applied:
        # The close runs before the tag clear so it can tell the superseded
        # version's edges from the ones this job just wrote.
        parts_closed = await apply_plan_after_fold(txn, job_id=job_id, plan=plan)
    await clear_job_tags(txn, job_id=job_id)
    committed = await txn.execute_write(
        commit_job_query(),
        {
            "job_id": str(job_id),
            "lease_token": str(token),
            "component_seed_ids": [str(seed_id) for seed_id in component_seed_ids],
            "created_entity_ids": [str(entity_id) for entity_id in created_entity_ids],
        },
    )
    if not committed:
        raise CutoverJobLeaseError(f"Job {job_id} lost its lease before commit.")
    return parts_closed


async def _commit_pending_writes(
    *,
    job_id: UUID,
    token: UUID,
    graph_store: GraphStore,
    close_document_node_id: UUID | None,
    candidate_document_node_id: UUID | None,
    keep_node_ids: Sequence[UUID],
    component_seed_ids: Sequence[UUID],
    created_entity_ids: Sequence[UUID],
    deferred: DeferredWrites,
    vector_work: VectorWork,
    in_place: InPlaceRefresh | None,
    change: DocumentChange | None,
    lease_ttl_seconds: int,
) -> int:
    """Expose pending writes, close old edges and replace pending candidates.

    The deferred writes over committed rows run right after the flip, so a
    replay that hits a row another job owns fails the commit.
    When ``in_place`` is set, the committed evidence of its chunk ids is
    retracted before the replay: those chunk ids leave the relations they
    evidence, relations left with no evidence are deleted, and their committed
    MENTIONED_IN edges are dropped. The refreshed chunks are then stamped with
    the new extraction fingerprint, unless it is ``None``. The job's new
    relations are folded into their canonical ids in the same transaction, and
    a constraint conflict with another job's commit retries the commit.
    When ``change`` is set, its activation record is written in the same
    transaction, after the old edges are closed. A constraint conflict retries
    the commit under the held lease until one lease TTL has passed since the
    first failure. A write conflict retries only on a backend that rolls back
    a failed transaction.
    """
    job_arg = str(job_id)
    token_arg = str(token)
    seed_args = [str(seed_id) for seed_id in component_seed_ids]
    created_args = [str(entity_id) for entity_id in created_entity_ids]
    plan = CommitPlan(
        close_document_node_id=close_document_node_id,
        candidate_document_node_id=candidate_document_node_id,
        keep_node_ids=list(keep_node_ids),
        in_place=in_place,
        change=change,
        deferred=list(deferred.entries),
        vector_targets=list(vector_work.targets),
        vector_deletes=list(vector_work.deletes),
    )
    plan_json = _PLAN_ADAPTER.dump_json(plan).decode()

    async def begin_commit(txn: GraphStoreTransaction) -> int:
        started = await txn.execute_write(
            begin_commit_query(),
            {
                "job_id": job_arg,
                "lease_token": token_arg,
                "commit_plan": plan_json,
                "component_seed_ids": seed_args,
                "created_entity_ids": created_args,
            },
        )
        if not started:
            raise CutoverJobLeaseError(f"Job {job_arg} lost its lease before commit.")
        return await apply_commit_steps(
            txn,
            plan=plan,
            job_id=job_id,
            token=token,
            skip=0,
            docs_applied=False,
            component_seed_ids=component_seed_ids,
            created_entity_ids=created_entity_ids,
        )

    # A started commit keeps the steps it recorded as done, so the retry resumes
    # after them instead of running the whole commit again.
    def resume_commit(
        row: Mapping[str, Any],
    ) -> Callable[[GraphStoreTransaction], Awaitable[int]]:
        skip = int(row.get("commit_replayed") or 0)
        docs_applied = bool(row.get("commit_docs_applied"))
        recorded_parts_closed = int(row.get("parts_closed") or 0)

        async def finish_commit(txn: GraphStoreTransaction) -> int:
            fenced = await txn.execute_write(
                resume_commit_fence_query(),
                {"job_id": job_arg, "lease_token": token_arg},
            )
            if not fenced:
                raise CutoverJobLeaseError(
                    f"Job {job_arg} lost its lease before commit."
                )
            parts_closed = await apply_commit_steps(
                txn,
                plan=plan,
                job_id=job_id,
                token=token,
                skip=skip,
                docs_applied=docs_applied,
                component_seed_ids=component_seed_ids,
                created_entity_ids=created_entity_ids,
            )
            return recorded_parts_closed if docs_applied else parts_closed

        return finish_commit

    # Two jobs that commit the same new relation at once both try to give it
    # the canonical id, and the loser fails on the id constraint. The retry
    # reads the recorded steps and resumes after them. The failing statement
    # writes nothing, but a step without recorded progress that ran earlier in
    # the attempt does run again, as it does in recovery. A write conflict is
    # raised after a replay batch has written its rows, so the retry would
    # repeat those writes unless the backend rolls back the whole attempt. The
    # lease is held throughout, so the retries wait for the other job to finish.
    attempt: Callable[[GraphStoreTransaction], Awaitable[int]] = begin_commit
    first_failure_at: float | None = None
    delay = _COMMIT_RETRY_INITIAL_DELAY_SECONDS
    while True:
        try:
            return await graph_store.run_in_transaction(attempt)
        except (
            GraphStoreConstraintViolationError,
            GraphStoreWriteConflictError,
        ) as exc:
            write_conflict = isinstance(exc, GraphStoreWriteConflictError)
            if write_conflict and not graph_store.rolls_back_failed_transactions:
                raise
            now = time.monotonic()
            if first_failure_at is None:
                first_failure_at = now
            remaining = lease_ttl_seconds - (now - first_failure_at)
            if remaining <= 0:
                raise
            await asyncio.sleep(min(delay, remaining))
            if time.monotonic() - first_failure_at >= lease_ttl_seconds:
                raise
            delay = min(delay * 2, _COMMIT_RETRY_MAX_DELAY_SECONDS)
        row = await _read_job_row(graph_store, job_id=job_id)
        applied = _applied_parts_closed(row, token)
        if applied is not None:
            return applied
        attempt = resume_commit(row) if row.get("commit_started") else begin_commit


async def _build_vector_work(
    graph_store: GraphStore,
    deferred: DeferredWrites,
    change: DocumentChange | None,
) -> VectorWork:
    """Capture vector writes and purge candidates before the commit starts."""
    deletes: list[VectorTarget] = []
    if change is not None and change.verb == "purge":
        rows = await graph_store.execute_read(
            document_chunk_ids_query(),
            {"document_node_id": str(change.document_node_id)},
        )
        for row in rows:
            try:
                deletes.append(
                    VectorTarget(kind=VectorKind.CHUNK, id=UUID(str(row["id"])))
                )
            except (KeyError, TypeError, ValueError):
                continue
    return VectorWork(targets=list(deferred.vector_targets), deletes=deletes)


async def run_cutover_job(
    *,
    verb: Literal["add", "update", "delete_document", "purge_document"],
    document_key: str,
    affected_entity_ids: list[UUID],
    graph_store: GraphStore,
    settings: CutoverJobSettings,
    pending_write: Callable[[UUID], Awaitable[T]],
    cleanup: Callable[[list[UUID], list[UUID], list[UUID], VectorWork], Awaitable[S]],
    deferred: DeferredWrites,
    components: Sequence[MatchComponent] = (),
    close_document_node_id: UUID | None = None,
    in_place: InPlaceRefresh | None = None,
    keep_node_ids: Sequence[UUID] = (),
    candidate_document_node_id: UUID | None = None,
    created_entity_ids: Sequence[UUID] = (),
    change: DocumentChange | None = None,
    tracer: Tracer | None = None,
    vector_sync: VectorSync | None = None,
) -> tuple[T, S, int]:
    """Run one cutover job under a lease, from pending writes to cleanup.

    Args:
        verb: The document mutation the job performs.
        document_key: The key of the document the job holds the lease for.
        affected_entity_ids: The entities the job touches, for cleanup.
        graph_store: The store the job commits to.
        settings: Lease and renewal timing for the job.
        pending_write: Writes the job's pending rows. Receives the job id.
        cleanup: Removes superseded rows. Receives the affected entity ids,
            component seed ids, created entity ids and recorded vector work.
        deferred: The writes over committed rows that the commit replays.
        components: The resolver components the job rebuilt.
        close_document_node_id: The document whose open HAS_PART edges are
            closed by the commit, if any.
        candidate_document_node_id: The document whose old pending candidates
            the commit replaces, if any.
        in_place: The refresh of a document that keeps its chunks, if any. Its
            entity and relation evidence is replaced and its chunks are
            re-stamped in the commit transaction.
        keep_node_ids: Structure nodes that stay open when the old version is
            closed.
        created_entity_ids: The entities the job created. The pending write
            fills this list, so it is read after that write, like
            ``keep_node_ids``.
        change: The committed document change the commit records as an
            activation. None for a job that changes no content, such as an
            in-place refresh.
        tracer: Opens the job span. None disables it.
        vector_sync: Removes external vectors when pending graph rows roll back.

    Returns:
        The pending write result, the cleanup result, and the number of
        HAS_PART edges closed.

    Raises:
        CutoverJobLeaseError: The job lost its lease before commit or cleanup.
    """
    resolved_tracer = get_tracer(tracer)
    with resolved_tracer.start_as_current_span(
        "agrag.ingestion.cutover_job",
        attributes={"agrag.verb": verb, "agrag.document_key": document_key},
    ) as span:
        job_id, token = await _acquire_lease(
            document_key=document_key,
            verb=verb,
            affected_entity_ids=affected_entity_ids,
            graph_store=graph_store,
            settings=settings,
            vector_sync=vector_sync,
        )
        span.set_attribute("agrag.job_id", str(job_id))
        stop_renewal = asyncio.Event()
        renewal_stopped = asyncio.Event()
        renewal = asyncio.create_task(
            _renew_periodically(
                graph_store=graph_store,
                job_id=job_id,
                token=token,
                ttl_seconds=settings.lease_ttl_seconds,
                stop_event=stop_renewal,
                stopped_event=renewal_stopped,
            )
        )
        leased = asyncio.create_task(
            _run_leased(
                job_id=job_id,
                token=token,
                graph_store=graph_store,
                pending_write=pending_write,
                cleanup=cleanup,
                affected_entity_ids=affected_entity_ids,
                components=components,
                close_document_node_id=close_document_node_id,
                candidate_document_node_id=candidate_document_node_id,
                in_place=in_place,
                keep_node_ids=keep_node_ids,
                created_entity_ids=created_entity_ids,
                deferred=deferred,
                vector_sync=vector_sync,
                change=change,
                stop_renewal=stop_renewal,
                renewal_stopped=renewal_stopped,
                lease_ttl_seconds=settings.lease_ttl_seconds,
            )
        )
        try:
            done, _ = await asyncio.wait(
                (leased, renewal), return_when=asyncio.FIRST_COMPLETED
            )
            if leased in done:
                return await leased
            if stop_renewal.is_set():
                return await leased
            leased.cancel()
            await asyncio.gather(leased, return_exceptions=True)
            await renewal
            raise RuntimeError("Lease renewal stopped unexpectedly.")
        finally:
            if not leased.done():
                leased.cancel()
            if not renewal.done():
                renewal.cancel()
            await asyncio.gather(leased, renewal, return_exceptions=True)


async def _run_leased(
    *,
    job_id: UUID,
    token: UUID,
    graph_store: GraphStore,
    pending_write: Callable[[UUID], Awaitable[T]],
    cleanup: Callable[[list[UUID], list[UUID], list[UUID], VectorWork], Awaitable[S]],
    affected_entity_ids: list[UUID],
    components: Sequence[MatchComponent],
    close_document_node_id: UUID | None,
    candidate_document_node_id: UUID | None,
    in_place: InPlaceRefresh | None,
    keep_node_ids: Sequence[UUID],
    created_entity_ids: Sequence[UUID],
    deferred: DeferredWrites,
    vector_sync: VectorSync | None,
    change: DocumentChange | None,
    stop_renewal: asyncio.Event,
    renewal_stopped: asyncio.Event,
    lease_ttl_seconds: int,
) -> tuple[T, S, int]:
    """Run the pending, commit, and cleanup phases under a held lease."""
    try:
        pending_result = await pending_write(job_id)
    except (asyncio.CancelledError, Exception):
        await _rollback(
            graph_store=graph_store,
            job_id=job_id,
            token=token,
            vector_sync=vector_sync,
        )
        raise
    component_seed_ids = _component_seed_ids(components)
    created = list(created_entity_ids)
    try:
        vector_work = await _build_vector_work(graph_store, deferred, change)
    except (asyncio.CancelledError, Exception):
        await _rollback(
            graph_store=graph_store,
            job_id=job_id,
            token=token,
            vector_sync=vector_sync,
        )
        raise
    commit_task = asyncio.create_task(
        _commit_pending_writes(
            job_id=job_id,
            token=token,
            graph_store=graph_store,
            close_document_node_id=close_document_node_id,
            candidate_document_node_id=candidate_document_node_id,
            keep_node_ids=keep_node_ids,
            component_seed_ids=component_seed_ids,
            created_entity_ids=created,
            deferred=deferred,
            vector_work=vector_work,
            in_place=in_place,
            change=change,
            lease_ttl_seconds=lease_ttl_seconds,
        )
    )
    try:
        parts_closed = await asyncio.shield(commit_task)
    except asyncio.CancelledError:
        try:
            await asyncio.shield(commit_task)
        except Exception:  # noqa: BLE001
            await _settle_failed_commit(
                graph_store=graph_store,
                job_id=job_id,
                token=token,
                vector_sync=vector_sync,
            )
        raise
    except Exception:
        applied = await _settle_failed_commit(
            graph_store=graph_store,
            job_id=job_id,
            token=token,
            vector_sync=vector_sync,
        )
        if applied is None:
            raise
        parts_closed = applied
    job_arg = str(job_id)
    token_arg = str(token)
    started = await graph_store.execute_write(
        start_cleaning_query(), {"job_id": job_arg, "lease_token": token_arg}
    )
    if not started:
        raise CutoverJobLeaseError(f"Job {job_arg} lost its lease before cleanup.")
    cleanup_result = await cleanup(
        affected_entity_ids,
        component_seed_ids,
        created,
        vector_work,
    )
    if isinstance(cleanup_result, list) and any(
        isinstance(failure, StageFailure) for failure in cleanup_result
    ):
        stop_renewal.set()
        await renewal_stopped.wait()
        return pending_result, cleanup_result, parts_closed
    stop_renewal.set()
    await renewal_stopped.wait()
    finished = await graph_store.execute_write(
        finish_cleaning_query(), {"job_id": job_arg, "lease_token": token_arg}
    )
    if not finished:
        raise CutoverJobLeaseError(f"Job {job_arg} lost its lease after cleanup.")
    return pending_result, cleanup_result, parts_closed
