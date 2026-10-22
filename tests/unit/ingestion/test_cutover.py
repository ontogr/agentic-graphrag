"""Tests for the Cutover Job runner against scripted store fakes.

The fakes implement the exact semantics each query builder's docstring
promises — atomic MERGE on document_key, compare-and-swap on the fencing
token, expiry comparison on the lease, tag matching by property value —
so these tests prove the runner's orchestration properties (ordering,
rollback/roll-forward, cleanup scoping), not any one
query's text. Query text is covered by tests/unit/cypher; real MERGE and
constraint behavior under concurrency by the integration test instead.
"""

import asyncio
import copy
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import DeferredWrites
from agrag.cypher.cutover_job_write import (
    acquire_lease_query,
    begin_commit_query,
    begin_rollback_query,
    claim_pending_job_query,
    clear_pending_node_tags_query,
    commit_job_query,
    delete_pending_nodes_query,
    finish_cleaning_query,
    job_status_query,
    lock_rolling_back_job_query,
    record_parts_closed_query,
    renew_lease_query,
    rollback_job_query,
    start_cleaning_query,
    steal_terminal_job_query,
)
from agrag.cypher.entities import PENDING_TAGGED_NODE_LABELS
from agrag.cypher.relations import close_has_part_query
from agrag.graphdb.errors import GraphStoreWriteConflictError
from agrag.ingestion._cutover import (
    CutoverJobLeaseError,
    run_cutover_job,
)
from agrag.ingestion.settings import CutoverJobSettings


def _epoch_millis(moment: datetime) -> int:
    """Return ``moment`` as epoch milliseconds, the form the lease Cypher stores."""
    return int(moment.timestamp() * 1000)


class _FakeCutoverStore:
    """In-memory stand-in implementing the job queries' contracts."""

    def __init__(self) -> None:
        """Create the fake with an empty job table and no tagged nodes."""
        self.jobs: dict[str, dict[str, Any]] = {}
        self.nodes: list[dict[str, Any]] = []
        self.transactions: list[list[tuple[str, dict[str, Any]]]] = []
        self.fail_on: set[str] = set()
        self.executed: list[str] = []
        self.raise_after_applying: str | None = None
        self.finish_delay_seconds = 0.0

    async def execute_read(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Reads return nothing; the runner makes none today anyway."""
        return []

    async def execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Dispatch one job query against the in-memory job table."""
        params = parameters or {}
        self.executed.append(query)
        if query in self.fail_on:
            raise RuntimeError(f"injected failure for {query[:40]!r}")
        handler = self._handlers().get(query)
        if handler is None:
            raise AssertionError(f"unexpected query: {query!r}")
        rows = handler(params)
        if query == finish_cleaning_query() and self.finish_delay_seconds:
            await asyncio.sleep(self.finish_delay_seconds)
        return rows

    def _handlers(self) -> dict[str, Any]:
        """Map each job query to its in-memory implementation."""
        handlers: dict[str, Any] = {
            acquire_lease_query(): self._acquire,
            steal_terminal_job_query(): self._steal,
            begin_commit_query(): lambda p: self._transition(p, "pending", "pending"),
            commit_job_query(): lambda p: self._transition(p, "pending", "committed"),
            start_cleaning_query(): lambda p: self._transition(
                p, "committed", "cleaning"
            ),
            finish_cleaning_query(): lambda p: self._transition(p, "cleaning", "done"),
            renew_lease_query(): self._renew,
            begin_rollback_query(): self._begin_rollback,
            claim_pending_job_query(): self._claim_pending_rollback,
            job_status_query(): self._job_status,
            record_parts_closed_query(): self._record_parts_closed,
            lock_rolling_back_job_query(): self._lock_rolling_back,
            rollback_job_query(): self._rollback,
        }
        for label in PENDING_TAGGED_NODE_LABELS:
            handlers[clear_pending_node_tags_query(label)] = self._clear_tag
            handlers[delete_pending_nodes_query(label)] = self._delete_tagged_nodes
        return handlers

    def _acquire(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """MERGE on document_key: first claimant creates, others join it."""
        key = str(params["document_key"])
        job: dict[str, Any] | None = self.jobs.get(key)
        if job is None:
            job = {
                "id": str(params["job_id"]),
                "status": "pending",
                "verb": params["verb"],
                "lease_token": str(params["lease_token"]),
                "lease_expires_at": params["lease_expires_at"],
            }
            self.jobs[key] = job
        return [
            {
                "id": job["id"],
                "lease_token": job["lease_token"],
                "status": job["status"],
                "lease_expired": job["lease_expires_at"]
                < _epoch_millis(datetime.now(UTC)),
            }
        ]

    def _claim_pending_rollback(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Take over an expired rollback before another write can start."""
        job = next(
            (job for job in self.jobs.values() if job["id"] == params["job_id"]),
            None,
        )
        if (
            job is None
            or job["status"] not in {"pending", "rolling_back"}
            or job["lease_token"] != params["expected_lease_token"]
            or job["lease_expires_at"] >= _epoch_millis(datetime.now(UTC))
        ):
            return []
        job["status"] = "rolling_back"
        job["lease_token"] = str(params["lease_token"])
        job["lease_expires_at"] = params["lease_expires_at"]
        return [{"id": job["id"]}]

    def _steal(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Take over a job only when it is done or rolled back."""
        job = self.jobs.get(str(params["document_key"]))
        if job is None:
            return []
        if job["status"] in ("done", "rolled_back"):
            job["id"] = str(params["job_id"])
            job["status"] = "pending"
            job["verb"] = params["verb"]
            job["lease_token"] = str(params["lease_token"])
            job["lease_expires_at"] = params["lease_expires_at"]
            return [{"lease_token": job["lease_token"]}]
        return []

    def _transition(
        self, params: dict[str, Any], expected: str, nxt: str
    ) -> list[dict[str, Any]]:
        """Compare-and-swap a job's status while its caller holds a live lease."""
        for job in self.jobs.values():
            if (
                job["id"] == str(params["job_id"])
                and job["lease_token"] == str(params["lease_token"])
                and job["status"] == expected
                and job["lease_expires_at"] >= _epoch_millis(datetime.now(UTC))
            ):
                job["status"] = nxt
                return [{"id": job["id"]}]
        return []

    def _renew(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Extend the lease of the job holding the caller's token."""
        for job in self.jobs.values():
            if (
                job["id"] == str(params["job_id"])
                and job["lease_token"] == str(params["lease_token"])
                and job["status"]
                in {"pending", "rolling_back", "committed", "cleaning"}
                and job["lease_expires_at"] >= _epoch_millis(datetime.now(UTC))
            ):
                job["lease_expires_at"] = params["lease_expires_at"]
                return [{"id": job["id"]}]
        return []

    def _clear_tag(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Strip this job's pending tag from every tagged node."""
        job_id = str(params["job_id"])
        cleared = 0
        for node in self.nodes:
            if node["properties"].pop("_pending_job_id", None) == job_id:
                cleared += 1
        return [{"cleared": cleared}]

    def _delete_tagged_nodes(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Delete every node still tagged with this job."""
        job_id = str(params["job_id"])
        kept = [
            node
            for node in self.nodes
            if node["properties"].get("_pending_job_id") != job_id
        ]
        deleted = len(self.nodes) - len(kept)
        self.nodes = kept
        return [{"deleted": deleted}]

    def _rolling_back_job(self, params: dict[str, Any]) -> dict[str, Any] | None:
        """Return the job when it is rolling back under the caller's token."""
        return next(
            (
                job
                for job in self.jobs.values()
                if job["id"] == str(params["job_id"])
                and job["status"] == "rolling_back"
                and job["lease_token"] == str(params["lease_token"])
            ),
            None,
        )

    def _lock_rolling_back(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Confirm the rollback fence without changing the job."""
        job = self._rolling_back_job(params)
        return [] if job is None else [{"id": job["id"]}]

    def _rollback(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Delete the job node only while its rollback holds the fence."""
        job = self._rolling_back_job(params)
        if job is None:
            return []
        job_id = job["id"]
        self.jobs = {key: job for key, job in self.jobs.items() if job["id"] != job_id}
        return [{"id": job_id}]

    def _begin_rollback(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        job = next(
            (job for job in self.jobs.values() if job["id"] == str(params["job_id"])),
            None,
        )
        if (
            job is None
            or job["status"] != "pending"
            or job["lease_token"] != str(params["lease_token"])
        ):
            return []
        job["status"] = "rolling_back"
        return [{"id": job["id"]}]

    def _job_status(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        job = next(
            (job for job in self.jobs.values() if job["id"] == params["job_id"]), None
        )
        if job is None:
            return []
        return [
            {
                "status": job["status"],
                "lease_token": job["lease_token"],
                "parts_closed": job.get("parts_closed"),
            }
        ]

    def _record_parts_closed(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        job = next(
            (job for job in self.jobs.values() if job["id"] == params["job_id"]), None
        )
        if job is not None:
            job["parts_closed"] = params["parts_closed"]
        return []

    async def run_in_transaction(self, work: Any) -> Any:
        """Run work with a handle that records writes and joins this store."""
        runner = self

        class _Txn:
            async def execute_read(
                self, query: str, parameters: dict[str, Any] | None = None
            ) -> list[dict[str, Any]]:
                return await runner.execute_read(query, parameters)

            async def execute_write(
                self, query: str, parameters: dict[str, Any] | None = None
            ) -> list[dict[str, Any]]:
                runner.transactions[-1].append((query, parameters or {}))
                if query == close_has_part_query():
                    return [{"closed": 0}]
                return await runner.execute_write(query, parameters)

        runner.transactions.append([])
        snapshot = (copy.deepcopy(runner.jobs), copy.deepcopy(runner.nodes))
        try:
            result = await work(_Txn())
        except BaseException:
            runner.jobs, runner.nodes = snapshot
            raise
        if runner.raise_after_applying == commit_job_query():
            raise RuntimeError("injected error after applying query")
        return result


class _CommitBlockingStore(_FakeCutoverStore):
    """Pauses after an atomic commit reaches its transaction boundary."""

    def __init__(self) -> None:
        """Create a store whose transaction exit waits for the test."""
        super().__init__()
        self.commit_started = asyncio.Event()
        self.release_commit = asyncio.Event()

    async def run_in_transaction(self, work: Any) -> Any:
        """Run work and block after successful writes reach the commit edge."""
        runner = self

        class _Txn:
            async def execute_read(
                self, query: str, parameters: dict[str, Any] | None = None
            ) -> list[dict[str, Any]]:
                return await runner.execute_read(query, parameters)

            async def execute_write(
                self, query: str, parameters: dict[str, Any] | None = None
            ) -> list[dict[str, Any]]:
                runner.transactions[-1].append((query, parameters or {}))
                if query == close_has_part_query():
                    return [{"closed": 0}]
                return await runner.execute_write(query, parameters)

        runner.transactions.append([])
        result = await work(_Txn())
        runner.commit_started.set()
        await runner.release_commit.wait()
        return result


_REPLAY_QUERY = "UNWIND $records AS record MATCH (n {id: record.id}) RETURN n.id AS id"


class _ReplayConflictStore(_FakeCutoverStore):
    """Rolls a transaction's job table and nodes back when its work raises.

    The replay query reports every record as not written, which is what a
    row owned by another in-flight job looks like to the commit transaction.
    """

    async def run_in_transaction(self, work: Any) -> Any:
        """Run work, restoring the job table and nodes if it raises."""
        saved_jobs = copy.deepcopy(self.jobs)
        saved_nodes = copy.deepcopy(self.nodes)
        try:
            return await super().run_in_transaction(work)
        except Exception:
            self.jobs.clear()
            self.jobs.update(saved_jobs)
            self.nodes[:] = saved_nodes
            raise

    async def execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Report the replayed record as owned by another job."""
        if query == _REPLAY_QUERY:
            return [{"id": "entity-1", "written": False}]
        return await super().execute_write(query, parameters)


async def _noop_cleanup(
    affected_entity_ids: list[UUID],
    component_seed_ids: list[UUID],
    created_entity_ids: list[UUID],
) -> None:
    """Default cleanup step for jobs whose cleanup does nothing."""


def _write_job(pending_write, cleanup=_noop_cleanup, **kwargs) -> dict[str, Any]:
    """Common keyword arguments for run_cutover_job calls."""
    return {
        "verb": "add",
        "document_key": "doc-1",
        "affected_entity_ids": [],
        "graph_store": kwargs.pop("graph_store"),
        "settings": kwargs.pop("settings", CutoverJobSettings()),
        "pending_write": pending_write,
        "cleanup": cleanup,
        "deferred": kwargs.pop("deferred", DeferredWrites()),
        **kwargs,
    }


def _entity(entity_id: UUID) -> Entity:
    """Build a raw Entity with a fixed id."""
    return Entity(id=entity_id, label="Person", name=str(entity_id))


def _tag_node(job_id: UUID) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "labels": ["Entity"],
        "properties": {"_pending_job_id": str(job_id), "name": "x"},
    }


class TestRunCutoverJobLeaseFailure:
    """A live lease held elsewhere blocks the job before any write."""

    async def test_second_job_raises_and_writes_nothing(self) -> None:
        """A live foreign lease raises CutoverJobLeaseError before any write happens."""
        store = _FakeCutoverStore()
        # Simulate another worker's live job on the same document: an
        # acquire that returns a foreign token, then a steal that finds
        # the job neither expired nor terminal.
        store.jobs["doc-1"] = {
            "id": str(uuid4()),
            "status": "pending",
            "verb": "add",
            "lease_token": str(uuid4()),
            "lease_expires_at": _epoch_millis(datetime.now(UTC) + timedelta(hours=1)),
        }
        wrote: list[UUID] = []

        async def pending(job_id: UUID) -> None:
            wrote.append(job_id)

        with pytest.raises(CutoverJobLeaseError):
            await run_cutover_job(**_write_job(pending, graph_store=store))

        assert wrote == []
        assert store.nodes == []
        assert not store.transactions

    async def test_lost_lease_before_commit_rolls_back(self) -> None:
        """Losing the lease between pending-write and commit rolls the job back."""
        store = _FakeCutoverStore()
        holder = str(uuid4())
        stolen_job_id = str(uuid4())

        async def pending(job_id: UUID) -> None:
            # Between the runner's acquire and its commit, another worker
            # steals the expired lease, so the fencing check fails.
            store.jobs["doc-1"]["lease_expires_at"] = _epoch_millis(
                datetime.now(UTC) - timedelta(seconds=1)
            )
            store.jobs["doc-1"]["id"] = stolen_job_id
            store.jobs["doc-1"]["lease_token"] = holder
            store.nodes.append(_tag_node(job_id))

        with pytest.raises(CutoverJobLeaseError):
            await run_cutover_job(**_write_job(pending, graph_store=store))

        # The stale worker cannot delete rows after another worker takes over.
        assert store.nodes
        assert store.jobs["doc-1"]["id"] == stolen_job_id
        assert store.jobs["doc-1"]["lease_token"] == holder
        assert rollback_job_query() not in store.executed

    async def test_expired_lease_before_commit_rolls_back(self) -> None:
        """An unclaimed expired lease cannot commit pending work."""
        store = _FakeCutoverStore()

        async def pending(job_id: UUID) -> None:
            store.jobs["doc-1"]["lease_expires_at"] = _epoch_millis(
                datetime.now(UTC) - timedelta(seconds=1)
            )
            store.nodes.append(_tag_node(job_id))

        with pytest.raises(CutoverJobLeaseError, match="lost its lease before commit"):
            await run_cutover_job(**_write_job(pending, graph_store=store))

        assert store.nodes == []
        assert store.jobs == {}


class TestRunCutoverJobLeaseRenewal:
    """The runner keeps its lease live for phases longer than the TTL."""

    async def test_done_transition_does_not_cancel_the_runner(self) -> None:
        """A renewal ending during the done transition leaves the call successful."""
        store = _FakeCutoverStore()
        store.finish_delay_seconds = 0.5

        async def pending(job_id: UUID) -> None:
            store.nodes.append(_tag_node(job_id))

        await asyncio.wait_for(
            run_cutover_job(
                **_write_job(
                    pending,
                    graph_store=store,
                    settings=CutoverJobSettings(lease_ttl_seconds=1),
                )
            ),
            timeout=2,
        )

        assert store.jobs["doc-1"]["status"] == "done"

    async def test_lost_lease_cancels_pending_write_and_rolls_back(self) -> None:
        """An empty renewal result stops a pending write before it can continue."""
        store = _FakeCutoverStore()
        store._renew = lambda params: []  # type: ignore[method-assign]
        pending_started = asyncio.Event()
        pending_cancelled = False

        async def pending(job_id: UUID) -> None:
            nonlocal pending_cancelled
            store.nodes.append(_tag_node(job_id))
            pending_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                pending_cancelled = True

        with pytest.raises(CutoverJobLeaseError, match="lost its lease"):
            await asyncio.wait_for(
                run_cutover_job(
                    **_write_job(
                        pending,
                        graph_store=store,
                        settings=CutoverJobSettings(lease_ttl_seconds=1),
                    )
                ),
                timeout=2,
            )

        assert pending_started.is_set()
        assert pending_cancelled
        assert store.nodes == []
        assert store.jobs == {}

    async def test_renewal_error_cancels_pending_write_and_rolls_back(self) -> None:
        """A renewal error propagates after stopping and rolling back pending work."""
        store = _FakeCutoverStore()
        store.fail_on.add(renew_lease_query())
        pending_cancelled = False

        async def pending(job_id: UUID) -> None:
            nonlocal pending_cancelled
            store.nodes.append(_tag_node(job_id))
            try:
                await asyncio.Event().wait()
            finally:
                pending_cancelled = True

        with pytest.raises(RuntimeError, match="injected failure"):
            await asyncio.wait_for(
                run_cutover_job(
                    **_write_job(
                        pending,
                        graph_store=store,
                        settings=CutoverJobSettings(lease_ttl_seconds=1),
                    )
                ),
                timeout=2,
            )

        assert pending_cancelled
        assert store.nodes == []
        assert store.jobs == {}

    async def test_lost_lease_cancels_cleanup_without_rolling_back(self) -> None:
        """An empty renewal result leaves committed work for roll-forward."""
        store = _FakeCutoverStore()
        store._renew = lambda params: []  # type: ignore[method-assign]
        cleanup_started = asyncio.Event()
        cleanup_cancelled = False

        async def pending(job_id: UUID) -> None:
            store.nodes.append(_tag_node(job_id))

        async def cleanup(
            affected: list[UUID], seeds: list[UUID], created: list[UUID]
        ) -> None:
            nonlocal cleanup_cancelled
            cleanup_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleanup_cancelled = True

        with pytest.raises(CutoverJobLeaseError, match="lost its lease"):
            await asyncio.wait_for(
                run_cutover_job(
                    **_write_job(
                        pending,
                        cleanup,
                        graph_store=store,
                        settings=CutoverJobSettings(lease_ttl_seconds=1),
                    )
                ),
                timeout=2,
            )

        assert cleanup_started.is_set()
        assert cleanup_cancelled
        assert store.nodes
        assert all("_pending_job_id" not in node["properties"] for node in store.nodes)
        assert store.jobs["doc-1"]["status"] == "cleaning"


class TestRunCutoverJobRollback:
    """A pending_write failure rolls everything back."""

    async def test_new_write_recovers_expired_pending_job_first(self) -> None:
        """A later write rolls back an expired pending job before its own write."""
        store = _FakeCutoverStore()
        old_job_id = uuid4()
        store.jobs["doc-1"] = {
            "id": str(old_job_id),
            "status": "pending",
            "lease_token": str(uuid4()),
            "lease_expires_at": _epoch_millis(datetime.now(UTC) - timedelta(seconds=1)),
        }
        store.nodes.append(_tag_node(old_job_id))
        old_rows_seen_by_pending_write: list[bool] = []

        async def pending(job_id: UUID) -> None:
            old_rows_seen_by_pending_write.append(
                any(
                    node["properties"].get("_pending_job_id") == str(old_job_id)
                    for node in store.nodes
                )
            )
            store.nodes.append(_tag_node(job_id))

        await run_cutover_job(**_write_job(pending, graph_store=store))

        assert old_rows_seen_by_pending_write == [False]
        assert old_job_id != UUID(store.jobs["doc-1"]["id"])
        assert all(
            node["properties"].get("_pending_job_id") != str(old_job_id)
            for node in store.nodes
        )

    async def test_pending_write_failure_deletes_tagged_writes(self) -> None:
        """A pending-write failure deletes tagged nodes and the job record."""
        store = _FakeCutoverStore()

        async def pending(job_id: UUID) -> None:
            store.nodes.append(_tag_node(job_id))
            raise RuntimeError("extraction blew up")

        with pytest.raises(RuntimeError, match="extraction blew up"):
            await run_cutover_job(**_write_job(pending, graph_store=store))

        assert store.nodes == []
        assert "doc-1" not in store.jobs
        # Cleanup never ran: the job never committed.
        assert commit_job_query() not in store.executed

    async def test_commit_transaction_failure_rolls_back(self) -> None:
        """A failure inside the commit transaction rolls the pending writes back too."""
        store = _FakeCutoverStore()
        store.fail_on.add(commit_job_query())

        async def pending(job_id: UUID) -> None:
            store.nodes.append(_tag_node(job_id))

        with pytest.raises(RuntimeError, match="injected failure"):
            await run_cutover_job(**_write_job(pending, graph_store=store))

        assert store.nodes == []
        assert "doc-1" not in store.jobs

    async def test_rollback_errors_are_suppressed(self) -> None:
        """A failing rollback still lets the original error propagate."""
        store = _FakeCutoverStore()
        # Rollback itself fails; the original error still propagates.
        store.fail_on.add(rollback_job_query())

        async def pending(job_id: UUID) -> None:
            raise RuntimeError("original failure")

        with pytest.raises(RuntimeError, match="original failure"):
            await run_cutover_job(**_write_job(pending, graph_store=store))


class TestRunCutoverJobReplay:
    """A deferred write that the commit cannot apply fails the whole commit."""

    async def test_replay_conflict_rolls_job_back_and_never_commits(self) -> None:
        """A replay that finds a row another job owns rolls the job back."""
        store = _ReplayConflictStore()
        deferred = DeferredWrites()

        async def pending(job_id: UUID) -> None:
            store.nodes.append(_tag_node(job_id))
            deferred.add_unwritten(
                _REPLAY_QUERY,
                [{"id": "entity-1", "pending_job_id": str(job_id), "properties": {}}],
                [{"id": "entity-1", "written": False}],
            )

        with pytest.raises(GraphStoreWriteConflictError):
            await run_cutover_job(
                **_write_job(pending, graph_store=store, deferred=deferred)
            )

        assert store.nodes == []
        assert "doc-1" not in store.jobs


class TestRunCutoverJobRollForward:
    """A cleanup failure leaves the job committed for a later resume."""

    async def test_cancellation_after_commit_preserves_recovery_record(self) -> None:
        """Cancellation after a commit keeps its data and job for recovery."""
        store = _CommitBlockingStore()

        async def pending(job_id: UUID) -> None:
            store.nodes.append(_tag_node(job_id))

        task = asyncio.create_task(
            run_cutover_job(**_write_job(pending, graph_store=store))
        )
        await asyncio.wait_for(store.commit_started.wait(), timeout=1)
        task.cancel()
        store.release_commit.set()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert store.nodes
        assert all("_pending_job_id" not in node["properties"] for node in store.nodes)
        assert store.jobs["doc-1"]["status"] == "committed"

    async def test_finish_cleaning_fence_failure_after_cleanup(self) -> None:
        """Losing the lease before the done flip parks the job in cleaning."""
        store = _FakeCutoverStore()
        # The cleaning transition succeeds, so cleanup runs, but the done
        # flip loses the lease — the resume hook finishes the job later.
        original_transition = store._transition

        def flaky_finish(params: dict[str, Any], expected: str, nxt: str):
            if expected == "cleaning" and nxt == "done":
                return []
            return original_transition(params, expected, nxt)

        store._transition = flaky_finish  # type: ignore[method-assign]

        async def pending(job_id: UUID) -> None:
            store.nodes.append(_tag_node(job_id))

        cleaned = False

        async def cleanup(
            affected: list[UUID], seeds: list[UUID], created: list[UUID]
        ) -> None:
            nonlocal cleaned
            cleaned = True

        with pytest.raises(CutoverJobLeaseError):
            await run_cutover_job(**_write_job(pending, cleanup, graph_store=store))

        assert cleaned
        assert store.nodes
        assert store.jobs["doc-1"]["status"] == "cleaning"


class TestAmbiguousCommit:
    """An applied commit that raises on the client remains committed."""

    async def test_unreadable_status_leaves_job_for_recovery(self) -> None:
        """An unreadable write-routed status never triggers rollback."""
        store = _FakeCutoverStore()
        store.raise_after_applying = commit_job_query()
        store.fail_on.add(job_status_query())

        async def pending(job_id: UUID) -> None:
            store.nodes.append(_tag_node(job_id))

        with pytest.raises(RuntimeError, match="after applying"):
            await run_cutover_job(**_write_job(pending, graph_store=store))

        assert rollback_job_query() not in store.executed
        assert store.jobs["doc-1"]["status"] == "committed"
        assert store.nodes

    async def test_applied_commit_continues_cleanup_and_returns_recorded_count(
        self,
    ) -> None:
        """A readable applied commit proceeds through cleanup with its count."""
        store = _FakeCutoverStore()
        store.raise_after_applying = commit_job_query()

        async def pending(job_id: UUID) -> None:
            store.nodes.append(_tag_node(job_id))

        result = await run_cutover_job(**_write_job(pending, graph_store=store))

        assert result[2] == 0
        assert store.jobs["doc-1"]["parts_closed"] == 0
        assert store.jobs["doc-1"]["status"] == "done"
        assert rollback_job_query() not in store.executed

    async def test_recovery_owned_commit_is_still_reported_as_applied(self) -> None:
        """A recovery claim after commit preserves the applied result."""
        store = _FakeCutoverStore()
        store.raise_after_applying = commit_job_query()
        original_status = store._job_status

        def recovery_claim(params: dict[str, Any]) -> list[dict[str, Any]]:
            job = store.jobs["doc-1"]
            job["status"] = "cleaning"
            job["lease_token"] = str(uuid4())
            job["parts_closed"] = 7
            return original_status(params)

        store._job_status = recovery_claim  # type: ignore[method-assign]

        async def pending(job_id: UUID) -> None:
            store.nodes.append(_tag_node(job_id))

        with pytest.raises(CutoverJobLeaseError, match="lost its lease"):
            await run_cutover_job(**_write_job(pending, graph_store=store))

        assert rollback_job_query() not in store.executed


class TestRunCutoverJobComponentSeeds:
    """The commit records which components the cleanup phase must rebuild."""

    async def test_commit_records_one_seed_per_component(self) -> None:
        """The commit stores each component's lowest member id, and cleanup gets it."""
        store = _FakeCutoverStore()
        low, high, other_low, other_high = sorted(uuid4() for _ in range(4))
        components = [
            ([], [_entity(high), _entity(low)]),
            ([], [_entity(other_high), _entity(other_low)]),
        ]
        received: list[tuple[list[UUID], list[UUID]]] = []

        async def pending(job_id: UUID) -> None:
            return None

        async def cleanup(
            affected: list[UUID], seeds: list[UUID], created: list[UUID]
        ) -> None:
            received.append((affected, seeds))

        affected = [uuid4()]
        await run_cutover_job(
            **_write_job(
                pending,
                cleanup,
                graph_store=store,
                affected_entity_ids=affected,
                components=components,
            )
        )

        committed = [
            params
            for transaction in store.transactions
            for query, params in transaction
            if query == commit_job_query()
        ]
        expected = sorted([low, other_low], key=str)
        assert len(committed) == 1
        assert sorted(committed[0]["component_seed_ids"]) == [
            str(seed) for seed in expected
        ]
        assert len(received) == 1
        assert received[0][0] == affected
        assert sorted(received[0][1], key=str) == expected

    async def test_components_found_by_pending_write_are_recorded(self) -> None:
        """A component appended while pending_write runs still reaches the commit."""
        store = _FakeCutoverStore()
        components: list[Any] = []
        member_ids = [uuid4(), uuid4()]

        async def pending(job_id: UUID) -> None:
            components.append(([], [_entity(member) for member in member_ids]))

        await run_cutover_job(
            **_write_job(pending, graph_store=store, components=components)
        )

        committed = [
            params
            for transaction in store.transactions
            for query, params in transaction
            if query == commit_job_query()
        ]
        assert committed[0]["component_seed_ids"] == [str(min(member_ids, key=str))]
