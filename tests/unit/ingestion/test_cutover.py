"""Tests for the Cutover Job runner against scripted store fakes.

The fakes implement the exact semantics each query builder's docstring
promises — atomic MERGE on document_key, compare-and-swap on the fencing
token, expiry comparison on the lease, tag matching by property value —
so these tests prove the runner's orchestration properties (ordering,
rollback/roll-forward, cleanup scoping, lease release), not any one
query's text. Query text is covered by tests/unit/cypher; real MERGE and
constraint behavior under concurrency by the integration test instead.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.vector_record import VectorRecord
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
from agrag.cypher.relations import close_part_of_query
from agrag.ingestion._cutover import (
    CutoverJobLeaseError,
    clear_pending_vectors,
    run_cutover_job,
)
from agrag.ingestion.settings import CutoverJobSettings


class _FakeCutoverStore:
    """In-memory stand-in implementing the job queries' contracts."""

    def __init__(self) -> None:
        """Create the fake with an empty job table and no tagged nodes."""
        self.jobs: dict[str, dict[str, Any]] = {}
        self.nodes: list[dict[str, Any]] = []
        self.transactions: list[list[tuple[str, dict[str, Any]]]] = []
        self.fail_on: set[str] = set()

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
        if query in self.fail_on:
            raise RuntimeError(f"injected failure for {query[:40]!r}")
        handler = self._handlers().get(query)
        if handler is None:
            raise AssertionError(f"unexpected query: {query!r}")
        return handler(params)

    def _handlers(self) -> dict[str, Any]:
        """Map each job query to its in-memory implementation."""
        return {
            acquire_lease_query(): self._acquire,
            steal_expired_lease_query(): self._steal,
            commit_job_query(): lambda p: self._transition(p, "pending", "committed"),
            start_cleaning_query(): lambda p: self._transition(
                p, "committed", "cleaning"
            ),
            finish_cleaning_query(): lambda p: self._transition(p, "cleaning", "done"),
            renew_lease_query(): self._renew,
            clear_pending_tag_query(): self._clear_tag,
            rollback_job_query(): self._rollback,
        }

    def _acquire(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """MERGE on document_key: first claimant creates, others join it."""
        key = str(params["document_key"])
        job = self.jobs.get(key)
        if job is None:
            job = {
                "id": str(params["job_id"]),
                "status": "pending",
                "verb": params["verb"],
                "lease_token": str(params["lease_token"]),
                "lease_expires_at": datetime.fromisoformat(
                    str(params["lease_expires_at"])
                ),
            }
            self.jobs[key] = job
        return [{"lease_token": job["lease_token"], "status": job["status"]}]

    def _steal(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Take over a job only when its lease lapsed or it went terminal."""
        job = self.jobs.get(str(params["document_key"]))
        if job is None:
            return []
        expired = job["lease_expires_at"] < datetime.now(UTC)
        if job["status"] == "done" or (job["status"] == "pending" and expired):
            job["id"] = str(params["job_id"])
            job["status"] = "pending"
            job["verb"] = params["verb"]
            job["lease_token"] = str(params["lease_token"])
            job["lease_expires_at"] = datetime.fromisoformat(
                str(params["lease_expires_at"])
            )
            return [{"lease_token": job["lease_token"]}]
        return []

    def _transition(
        self, params: dict[str, Any], expected: str, nxt: str
    ) -> list[dict[str, Any]]:
        """Compare-and-swap a job's status, fenced by its lease token."""
        for job in self.jobs.values():
            if (
                job["id"] == str(params["job_id"])
                and job["lease_token"] == str(params["lease_token"])
                and job["status"] == expected
            ):
                job["status"] = nxt
                return [{"id": job["id"]}]
        return []

    def _renew(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Extend the lease of the job holding the caller's token."""
        for job in self.jobs.values():
            if job["id"] == str(params["job_id"]) and job["lease_token"] == str(
                params["lease_token"]
            ):
                job["lease_expires_at"] = datetime.fromisoformat(
                    str(params["lease_expires_at"])
                )
                return [{"id": job["id"]}]
        return []

    def _clear_tag(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Strip this job's pending tag from every tagged node."""
        job_id = str(params["job_id"])
        for node in self.nodes:
            if node["properties"].get("_pending_job_id") == job_id:
                node["properties"].pop("_pending_job_id", None)
        return [{"cleared_nodes": len(self.nodes), "cleared_relationships": 0}]

    def _rollback(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Delete every tagged node and the completed job record."""
        job_id = str(params["job_id"])
        self.nodes = [
            node
            for node in self.nodes
            if node["properties"].get("_pending_job_id") != job_id
        ]
        self.jobs = {key: job for key, job in self.jobs.items() if job["id"] != job_id}
        return [{"deleted_nodes": 0, "deleted_relationships": 0}]

    def transaction(self) -> Any:
        """Yield a handle that records writes and joins this store's table."""
        runner = self

        class _Txn:
            async def __aenter__(self) -> "_Txn":
                runner.transactions.append([])
                return self

            async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
                return None

            async def execute_write(
                self, query: str, parameters: dict[str, Any] | None = None
            ) -> list[dict[str, Any]]:
                runner.transactions[-1].append((query, parameters or {}))
                if query == close_part_of_query():
                    return [{"closed": 0}]
                return await runner.execute_write(query, parameters)

        return _Txn()


class _FakeVectorStore:
    """Records upserts; scrolls back only what it was handed."""

    def __init__(self) -> None:
        """Create the fake with empty collections."""
        self.records: dict[str, dict[str, Any]] = {}
        self.upsert_calls = 0

    async def scroll(
        self,
        collection: str,
        *,
        limit: int = 100,
        page_offset: str | None = None,
        filters: dict[str, Any] | None = None,
        with_vectors: bool = False,
    ) -> tuple[list[Any], str | None]:
        """Return records whose payload matches the filter, in one page."""
        job_id = (filters or {}).get("_pending_job_id")
        matches = [
            record
            for record in self.records.get(collection, {}).values()
            if record.payload.get("_pending_job_id") == job_id
        ]
        return matches, None

    async def upsert(self, collection: str, records: list[Any]) -> None:
        """Store the records by id, like the real backends."""
        self.upsert_calls += 1
        bucket = self.records.setdefault(collection, {})
        for record in records:
            bucket[str(record.id)] = record

    async def delete(self, collection: str, ids: list[str]) -> None:
        """Drop the ids from the collection."""
        bucket = self.records.get(collection, {})
        for record_id in ids:
            bucket.pop(str(record_id), None)


async def _noop_cleanup() -> None:
    """Default cleanup step for jobs whose cleanup does nothing."""


def _write_job(pending_write, cleanup=_noop_cleanup, **kwargs) -> dict[str, Any]:
    """Common keyword arguments for run_cutover_job calls."""
    return {
        "verb": "add",
        "document_key": "doc-1",
        "affected_entity_ids": [],
        "graph_store": kwargs.pop("graph_store"),
        "vector_store": kwargs.pop("vector_store", None),
        "vector_collections": kwargs.pop("vector_collections", ("col-a",)),
        "settings": kwargs.pop("settings", CutoverJobSettings()),
        "pending_write": pending_write,
        "cleanup": cleanup,
        **kwargs,
    }


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
            "lease_expires_at": datetime.now(UTC) + timedelta(hours=1),
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
            store.jobs["doc-1"]["lease_expires_at"] = datetime.now(UTC) - timedelta(
                seconds=1
            )
            store.jobs["doc-1"]["id"] = stolen_job_id
            store.jobs["doc-1"]["lease_token"] = holder
            store.nodes.append(_tag_node(job_id))

        with pytest.raises(CutoverJobLeaseError):
            await run_cutover_job(**_write_job(pending, graph_store=store))

        # Rollback removes tagged nodes and the job record.
        assert store.nodes == []
        assert store.jobs["doc-1"]["id"] == stolen_job_id
        assert store.jobs["doc-1"]["lease_token"] == holder


class TestRunCutoverJobLeaseRenewal:
    """The runner keeps its lease live for phases longer than the TTL."""

    async def test_lease_outlives_a_slow_pending_write(self) -> None:
        """A write slower than the TTL never exposes an expired lease."""
        store = _FakeCutoverStore()
        expired_seen: list[bool] = []

        async def slow_write(job_id: UUID) -> None:
            await asyncio.sleep(1.3)
            job = store.jobs["doc-1"]
            expired_seen.append(job["lease_expires_at"] < datetime.now(UTC))

        await run_cutover_job(
            **_write_job(
                slow_write,
                graph_store=store,
                settings=CutoverJobSettings(lease_ttl_seconds=1),
            )
        )
        assert store.jobs["doc-1"]["status"] == "done"
        assert not any(expired_seen)


class TestRunCutoverJobRollback:
    """A pending_write failure rolls everything back."""

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
        assert store.transactions == []

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

    async def test_pending_write_failure_deletes_pending_vectors(self) -> None:
        """Rollback deletes the job's pending vectors, not just graph rows.

        A rolled-back job's writes were never committed; leaving its
        pending-tagged vectors behind would orphan them permanently, since
        nothing else ever revisits a rolled-back job's id.
        """
        store = _FakeCutoverStore()
        vector_store = _FakeVectorStore()

        async def pending(job_id: UUID) -> None:
            await vector_store.upsert(
                "col-a",
                [
                    VectorRecord(
                        id=uuid4(),
                        vector=[0.0],
                        payload={"_pending_job_id": str(job_id), "_pending": True},
                    )
                ],
            )
            raise RuntimeError("extraction blew up")

        with pytest.raises(RuntimeError, match="extraction blew up"):
            await run_cutover_job(
                **_write_job(pending, graph_store=store, vector_store=vector_store)
            )

        assert vector_store.records["col-a"] == {}


class TestRunCutoverJobRollForward:
    """A cleanup failure leaves the job committed for a later resume."""

    async def test_cleanup_failure_leaves_committed_data(self) -> None:
        """A cleanup failure leaves committed data, job parked in cleaning."""
        store = _FakeCutoverStore()

        async def pending(job_id: UUID) -> None:
            store.nodes.append(_tag_node(job_id))

        async def cleanup() -> None:
            raise RuntimeError("pruning blew up")

        with pytest.raises(RuntimeError, match="pruning blew up"):
            await run_cutover_job(**_write_job(pending, cleanup, graph_store=store))

        # The writes survived, tags cleared, job parked in cleaning — the
        # state a Graph.open() resume hook rolls forward.
        assert store.nodes
        assert all("_pending_job_id" not in n["properties"] for n in store.nodes)
        assert store.jobs["doc-1"]["status"] == "cleaning"

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

        async def cleanup() -> None:
            nonlocal cleaned
            cleaned = True

        with pytest.raises(CutoverJobLeaseError):
            await run_cutover_job(**_write_job(pending, cleanup, graph_store=store))

        assert cleaned
        assert store.nodes
        assert store.jobs["doc-1"]["status"] == "cleaning"


class TestClearPendingVectors:
    """The vector half of the commit clears only this job's payloads."""

    async def test_clears_only_this_job_records(self) -> None:
        """Only this job's payloads flip to committed; other records are untouched."""
        vector_store = _FakeVectorStore()
        job_id = uuid4()
        other = uuid4()

        vector_store.records["col-a"] = {
            str(job_id): VectorRecord(
                id=job_id,
                vector=[0.1],
                payload={"text": "t", "_pending": True, "_pending_job_id": str(job_id)},
            ),
            str(other): VectorRecord(
                id=other,
                vector=[0.2],
                payload={"text": "u", "_pending": False},
            ),
        }

        await clear_pending_vectors(
            vector_store=vector_store, collections=("col-a",), job_id=job_id
        )

        cleared = vector_store.records["col-a"][str(job_id)]
        untouched = vector_store.records["col-a"][str(other)]
        assert cleared.payload["_pending"] is False
        assert untouched.payload["_pending"] is False

    async def test_none_vector_store_is_a_noop(self) -> None:
        """A None vector store clears nothing and does not raise."""
        await clear_pending_vectors(
            vector_store=None, collections=("col-a",), job_id=uuid4()
        )
