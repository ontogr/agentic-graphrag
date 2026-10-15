"""Crash-safe runner wrapping add/update/delete_document mutations.

``Graph`` stays the orchestrator; the job state machine lives here, taking
every dependency explicitly rather than reaching into ``Graph``.
"""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, TypeVar
from uuid import NAMESPACE_OID, UUID, uuid4, uuid5

from opentelemetry.trace import Tracer

from agrag.common.data_models.graph_record import DeferredWrites
from agrag.cypher.candidates import (
    delete_reviewed_job_candidates_query,
    delete_stale_candidates_query,
)
from agrag.cypher.cutover_job_write import (
    acquire_lease_query,
    begin_rollback_query,
    claim_pending_job_query,
    commit_job_query,
    finish_cleaning_query,
    job_status_query,
    record_parts_closed_query,
    renew_lease_query,
    start_cleaning_query,
    steal_terminal_job_query,
)
from agrag.cypher.documents import (
    record_activation_query,
    retire_document_version_query,
    set_chunk_extraction_fingerprint_query,
)
from agrag.cypher.relations import (
    delete_document_mentions_query,
    retract_document_relation_evidence_query,
)
from agrag.graphdb.base import GraphStore, GraphStoreTransaction
from agrag.graphdb.errors import GraphStoreConstraintViolationError
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

_COMMIT_ATTEMPTS = 3


async def _acquire_lease(
    *,
    document_key: str,
    verb: Literal["add", "update", "delete_document"],
    affected_entity_ids: list[UUID],
    graph_store: GraphStore,
    settings: CutoverJobSettings,
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
                "lease_expires_at": (
                    now + timedelta(seconds=settings.lease_ttl_seconds)
                ).isoformat(),
            },
        )
        if claimed:
            rollback_job_id = UUID(str(rows[0]["id"]))
            rolled_back = await rollback_job_rows(
                graph_store, job_id=rollback_job_id, token=rollback_token
            )
            if rolled_back:
                return await _acquire_lease(
                    document_key=document_key,
                    verb=verb,
                    affected_entity_ids=affected_entity_ids,
                    graph_store=graph_store,
                    settings=settings,
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
                    "lease_expires_at": (
                        datetime.now(UTC) + timedelta(seconds=ttl_seconds)
                    ).isoformat(),
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
) -> bool:
    """Delete pending writes only after a token-fenced rollback transition.

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
        return await rollback_job_rows(graph_store, job_id=job_id, token=token)
    except Exception:  # noqa: BLE001
        return False


async def _commit_applied(
    *, graph_store: GraphStore, job_id: UUID, token: UUID
) -> int | None:
    """Read the committed result through the write-routed database path.

    Returns:
        The recorded parts-closed count when this token committed the job
        or recovery has advanced it to cleaning or done. None when the job
        is absent, uncommitted, or still committed under another token.
    """
    rows = await graph_store.execute_write(job_status_query(), {"job_id": str(job_id)})
    if not rows:
        return None
    row = rows[0]
    if row.get("status") in {"cleaning", "done"}:
        return int(row.get("parts_closed") or 0)
    if row.get("status") == "committed" and row.get("lease_token") == str(token):
        return int(row.get("parts_closed") or 0)
    return None


async def _settle_failed_commit(
    *,
    graph_store: GraphStore,
    job_id: UUID,
    token: UUID,
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
    await _rollback(graph_store=graph_store, job_id=job_id, token=token)
    return None


def _component_seed_ids(components: Sequence[MatchComponent]) -> list[UUID]:
    """Return one member id for each component, the lowest by string order."""
    return [
        min((member.id for member in members), key=str)
        for _, members in components
        if members
    ]


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
    }


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
    in_place: InPlaceRefresh | None,
    change: DocumentChange | None,
) -> int:
    """Expose pending writes, close old edges and replace pending candidates.

    The deferred writes over committed rows run right after the flip, so a
    replay that hits a row another job owns rolls the whole commit back.
    When ``in_place`` is set, the committed evidence of its chunk ids is
    retracted before the replay: those chunk ids leave the relations they
    evidence, relations left with no evidence are deleted, and their committed
    MENTIONED_IN edges are dropped. The refreshed chunks are then stamped with
    the new extraction fingerprint, unless it is ``None``. The job's new
    relations are folded into their canonical ids in the same transaction, and
    the commit is retried when two jobs promote one relation at the same moment.
    When ``change`` is set, its activation record is written in the same
    transaction, after the old edges are closed.
    """
    job_arg = str(job_id)
    token_arg = str(token)

    async def commit(txn: GraphStoreTransaction) -> int:
        committed = await txn.execute_write(
            commit_job_query(),
            {
                "job_id": job_arg,
                "lease_token": token_arg,
                "component_seed_ids": [str(seed_id) for seed_id in component_seed_ids],
                "created_entity_ids": [
                    str(entity_id) for entity_id in created_entity_ids
                ],
            },
        )
        if not committed:
            raise CutoverJobLeaseError(f"Job {job_arg} lost its lease before commit.")
        # The delete must precede the replay: the replay re-creates the edges
        # the new run found again. It only matches committed edges, so the
        # job's own new edges, still tagged, survive.
        # Relations the new run finds again are deferred writes over committed
        # rows. The replay writes them back, including one deleted here, and
        # the relations it does not find stay gone. The retraction reads the
        # MENTIONED_IN edges, so it runs before they are deleted.
        if in_place is not None:
            refresh_params = {
                "document_node_id": str(in_place.document_node_id),
                "chunk_ids": [str(chunk_id) for chunk_id in in_place.chunk_ids],
            }
            await txn.execute_write(
                retract_document_relation_evidence_query(), refresh_params
            )
            await txn.execute_write(delete_document_mentions_query(), refresh_params)
        await replay_deferred(txn, deferred)
        await fold_job_relations(txn, job_id=job_id)
        if in_place is not None and in_place.extraction_fingerprint is not None:
            await txn.execute_write(
                set_chunk_extraction_fingerprint_query(),
                {
                    "chunk_ids": [str(chunk_id) for chunk_id in in_place.chunk_ids],
                    "extraction_fingerprint": in_place.extraction_fingerprint,
                },
            )
        # The close runs before the tag clear so it can tell the
        # superseded version's edges from the ones this job just
        # wrote; both land in the same transaction as the flip.
        parts_closed = 0
        if close_document_node_id is not None:
            parts_closed = await close_open_has_part_edges(
                txn,
                document_node_id=close_document_node_id,
                job_id=job_id,
                keep_node_ids=keep_node_ids,
            )
        if candidate_document_node_id is not None:
            # A review can settle a key after extraction's early lookup.
            # Recheck while the new candidates are still invisible to readers.
            await txn.execute_write(
                delete_reviewed_job_candidates_query(), {"job_id": job_arg}
            )
            await txn.execute_write(
                delete_stale_candidates_query(),
                {"document_node_id": str(candidate_document_node_id)},
            )
        if change is not None:
            await txn.execute_write(
                record_activation_query(), _activation_params(job_id, change)
            )
            if change.verb == "delete":
                await txn.execute_write(
                    retire_document_version_query(),
                    {"document_node_id": str(change.document_node_id)},
                )
        await txn.execute_write(
            record_parts_closed_query(),
            {"job_id": job_arg, "parts_closed": parts_closed},
        )
        await clear_job_tags(txn, job_id=job_id)
        return parts_closed

    # Two jobs that commit the same new relation at once both try to give it
    # the canonical id. The loser's transaction fails on the id constraint and
    # rolls back whole, so a second attempt finds the winner's edge and folds.
    for _ in range(_COMMIT_ATTEMPTS - 1):
        try:
            return await graph_store.run_in_transaction(commit)
        except GraphStoreConstraintViolationError:
            continue
    return await graph_store.run_in_transaction(commit)


async def run_cutover_job(
    *,
    verb: Literal["add", "update", "delete_document"],
    document_key: str,
    affected_entity_ids: list[UUID],
    graph_store: GraphStore,
    settings: CutoverJobSettings,
    pending_write: Callable[[UUID], Awaitable[T]],
    cleanup: Callable[[list[UUID], list[UUID], list[UUID]], Awaitable[S]],
    deferred: DeferredWrites,
    components: Sequence[MatchComponent] = (),
    close_document_node_id: UUID | None = None,
    in_place: InPlaceRefresh | None = None,
    keep_node_ids: Sequence[UUID] = (),
    candidate_document_node_id: UUID | None = None,
    created_entity_ids: Sequence[UUID] = (),
    change: DocumentChange | None = None,
    tracer: Tracer | None = None,
) -> tuple[T, S, int]:
    """Run one cutover job under a lease, from pending writes to cleanup.

    Args:
        verb: The document mutation the job performs.
        document_key: The key of the document the job holds the lease for.
        affected_entity_ids: The entities the job touches, for cleanup.
        graph_store: The store the job commits to.
        settings: Lease and renewal timing for the job.
        pending_write: Writes the job's pending rows. Receives the job id.
        cleanup: Removes superseded rows. Receives the affected entity ids, the
            component seed ids and the created entity ids.
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
                change=change,
                stop_renewal=stop_renewal,
                renewal_stopped=renewal_stopped,
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
    cleanup: Callable[[list[UUID], list[UUID], list[UUID]], Awaitable[S]],
    affected_entity_ids: list[UUID],
    components: Sequence[MatchComponent],
    close_document_node_id: UUID | None,
    candidate_document_node_id: UUID | None,
    in_place: InPlaceRefresh | None,
    keep_node_ids: Sequence[UUID],
    created_entity_ids: Sequence[UUID],
    deferred: DeferredWrites,
    change: DocumentChange | None,
    stop_renewal: asyncio.Event,
    renewal_stopped: asyncio.Event,
) -> tuple[T, S, int]:
    """Run the pending, commit, and cleanup phases under a held lease."""
    try:
        pending_result = await pending_write(job_id)
    except (asyncio.CancelledError, Exception):
        await _rollback(graph_store=graph_store, job_id=job_id, token=token)
        raise
    component_seed_ids = _component_seed_ids(components)
    created = list(created_entity_ids)
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
            in_place=in_place,
            change=change,
        )
    )
    try:
        parts_closed = await asyncio.shield(commit_task)
    except asyncio.CancelledError:
        try:
            await asyncio.shield(commit_task)
        except Exception:  # noqa: BLE001
            await _settle_failed_commit(
                graph_store=graph_store, job_id=job_id, token=token
            )
        raise
    except Exception:
        applied = await _settle_failed_commit(
            graph_store=graph_store, job_id=job_id, token=token
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
    cleanup_result = await cleanup(affected_entity_ids, component_seed_ids, created)
    stop_renewal.set()
    await renewal_stopped.wait()
    finished = await graph_store.execute_write(
        finish_cleaning_query(), {"job_id": job_arg, "lease_token": token_arg}
    )
    if not finished:
        raise CutoverJobLeaseError(f"Job {job_arg} lost its lease after cleanup.")
    return pending_result, cleanup_result, parts_closed
