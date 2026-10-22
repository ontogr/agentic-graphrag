"""Tests for the Graph.open() resume hook against a scripted store fake.

The fake implements find_incomplete_jobs_query, both recovery claims,
rollback_job_query, and finish_cleaning_query, mirroring the fake in
test_cutover.py. These tests prove resume_incomplete_jobs's orchestration
(which jobs it skips or rolls forward) rather than any one
query's text.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from agrag.common.data_models.stage_failure import StageFailure
from agrag.common.data_models.vector_record import VectorWork
from agrag.cypher.cutover_job_write import (
    claim_job_query,
    claim_pending_job_query,
    delete_pending_nodes_query,
    finish_cleaning_query,
    lock_rolling_back_job_query,
    renew_lease_query,
    rollback_job_query,
)
from agrag.cypher.entities import PENDING_TAGGED_NODE_LABELS
from agrag.cypher.schema import list_relation_types_query
from agrag.ingestion._resume import resume_incomplete_jobs


def _epoch_millis(moment: datetime) -> int:
    """Return ``moment`` as epoch milliseconds, the form the lease Cypher stores."""
    return int(moment.timestamp() * 1000)


_DELETE_NODES_QUERIES = {
    delete_pending_nodes_query(label) for label in PENDING_TAGGED_NODE_LABELS
}


class _FakeResumeStore:
    """In-memory stand-in exposing the queries resume_incomplete_jobs uses."""

    def __init__(self, jobs: list[dict[str, Any]]) -> None:
        """Seed the fake with the incomplete-job rows a read would return.

        Args:
            jobs: Each row as find_incomplete_jobs_query would shape it:
                id, status, affected_entity_ids, lease_expired, and an
                optional lease_token (generated when omitted).
        """
        self.jobs = {
            job["id"]: {**job, "lease_token": job.get("lease_token", str(uuid4()))}
            for job in jobs
        }
        self.finish_allowed = True
        self.finish_delay_seconds = 0.0
        self.renew_before_pending_claim = False
        self.renewal_count = 0
        self.rollback_count = 0
        self.rollback_tokens: list[str] = []

    async def execute_read(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Return every still-incomplete job's row, and no relationship types."""
        if query == list_relation_types_query():
            return []
        return [
            dict(job)
            for job in self.jobs.values()
            if job["status"] in {"pending", "rolling_back", "committed", "cleaning"}
        ]

    async def run_in_transaction(self, work: Any) -> Any:
        """Run the rollback work against this store as its transaction."""
        return await work(self)

    async def execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Dispatch one resume-phase query against the in-memory job table."""
        params = parameters or {}
        job_id = str(params.get("job_id"))
        if query in _DELETE_NODES_QUERIES:
            return [{"deleted": 0}]
        handler = self._handlers().get(query)
        if handler is None:
            raise AssertionError(f"unexpected query: {query!r}")
        rows = handler(job_id, params)
        if query == finish_cleaning_query() and self.finish_delay_seconds:
            await asyncio.sleep(self.finish_delay_seconds)
        return rows

    def _handlers(self) -> dict[str, Any]:
        """Map each resume-phase query to its in-memory implementation."""
        return {
            lock_rolling_back_job_query(): self._lock_rolling_back,
            rollback_job_query(): self._rollback_claimed,
            claim_job_query(): self._claim,
            claim_pending_job_query(): self._claim_pending,
            renew_lease_query(): self._renew,
            finish_cleaning_query(): self._finish,
        }

    def _claim(self, job_id: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Claim one committed or cleaning job for recovery."""
        job = self.jobs.get(job_id)
        if job is None or job["status"] not in ("committed", "cleaning"):
            return []
        job["status"] = "cleaning"
        job["lease_token"] = str(params["lease_token"])
        job["lease_expires_at"] = params["lease_expires_at"]
        return [{"status": job["status"]}]

    def _claim_pending(
        self, job_id: str, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Claim one lapsed pending job before deleting its tagged writes."""
        job = self.jobs.get(job_id)
        if job is None:
            return []
        if self.renew_before_pending_claim:
            job["lease_expired"] = False
        if (
            job["status"] not in ("pending", "rolling_back")
            or not job["lease_expired"]
            or job["lease_token"] != str(params["expected_lease_token"])
        ):
            return []
        job["status"] = "rolling_back"
        job["lease_token"] = str(params["lease_token"])
        job["lease_expires_at"] = params["lease_expires_at"]
        job["lease_expired"] = False
        return [{"id": job_id}]

    def _lock_rolling_back(
        self, job_id: str, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Confirm a rolling-back job is still held by the recovery claimant."""
        job = self.jobs.get(job_id)
        if (
            job is None
            or job["status"] != "rolling_back"
            or job["lease_token"] != str(params["lease_token"])
        ):
            return []
        return [{"id": job_id}]

    def _rollback_claimed(
        self, job_id: str, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Delete only a pending job held by the recovery claimant."""
        job = self.jobs.get(job_id)
        if (
            job is None
            or job["status"] != "rolling_back"
            or job["lease_token"] != str(params["lease_token"])
        ):
            return []
        self.rollback_count += 1
        self.rollback_tokens.append(str(params["lease_token"]))
        self.jobs.pop(job_id)
        return [{"deleted_nodes": 0, "deleted_relationships": 0}]

    def _renew(self, job_id: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Renew one active recovery claim while it remains live."""
        job = self.jobs.get(job_id)
        if (
            job is None
            or job["lease_token"] != str(params["lease_token"])
            or job["status"] not in ("pending", "committed", "cleaning")
            or job["lease_expires_at"] < _epoch_millis(datetime.now(UTC))
        ):
            return []
        job["lease_expires_at"] = params["lease_expires_at"]
        self.renewal_count += 1
        return [{"id": job_id}]

    def _finish(self, job_id: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Mark one live recovery claim done when its cleanup completes."""
        job = self.jobs.get(job_id)
        if (
            job is None
            or not self.finish_allowed
            or job["lease_token"] != str(params["lease_token"])
            or job["lease_expires_at"] < _epoch_millis(datetime.now(UTC))
        ):
            return []
        job["status"] = "done"
        return [{"id": job_id}]


class TestResumeIncompleteJobs:
    """resume_incomplete_jobs rolls back or forward, per job status."""

    @staticmethod
    async def test_uses_current_cutover_settings_when_called(monkeypatch) -> None:
        """An omitted lease duration comes from settings at invocation time."""
        job_id = str(uuid4())
        store = _FakeResumeStore(
            [
                {
                    "id": job_id,
                    "status": "committed",
                    "affected_entity_ids": [],
                    "lease_expired": True,
                }
            ]
        )
        monkeypatch.setenv("CUTOVER_JOB_LEASE_TTL_SECONDS", "23")
        started = datetime.now(UTC)

        handled = await resume_incomplete_jobs(store)
        finished = datetime.now(UTC)

        assert handled == [job_id]
        assert store.jobs[job_id]["status"] == "done"
        assert (
            _epoch_millis(started + timedelta(seconds=23))
            <= store.jobs[job_id]["lease_expires_at"]
            <= _epoch_millis(finished + timedelta(seconds=23))
        )

    async def test_pending_job_renewed_after_scan_is_not_rolled_back(self) -> None:
        """Recovery does not delete a job that renewed after its scan result."""
        job_id = str(uuid4())
        store = _FakeResumeStore(
            [
                {
                    "id": job_id,
                    "status": "pending",
                    "affected_entity_ids": [],
                    "lease_expired": True,
                }
            ]
        )
        store.renew_before_pending_claim = True

        handled = await resume_incomplete_jobs(store)

        assert handled == []
        assert store.jobs[job_id]["status"] == "pending"
        assert store.rollback_count == 0

    async def test_finishes_a_rolling_back_job(self) -> None:
        """Recovery reclaims an interrupted rollback and finishes its deletion."""
        job_id = str(uuid4())
        store = _FakeResumeStore(
            [
                {
                    "id": job_id,
                    "status": "rolling_back",
                    "affected_entity_ids": [],
                    "lease_expired": True,
                }
            ]
        )
        original_token = store.jobs[job_id]["lease_token"]

        handled = await resume_incomplete_jobs(store)

        assert handled == [job_id]
        assert store.rollback_count == 1
        assert store.rollback_tokens[0] != original_token
        assert job_id not in store.jobs

    async def test_roll_forward_receives_all_recorded_lists(self) -> None:
        """Cleanup gets the snapshot, component seeds and created entities."""
        job_id = str(uuid4())
        affected, seed, created = uuid4(), uuid4(), uuid4()
        store = _FakeResumeStore(
            [
                {
                    "id": job_id,
                    "status": "committed",
                    "affected_entity_ids": [str(affected)],
                    "component_seed_ids": [str(seed), "not-a-uuid"],
                    "created_entity_ids": [str(created)],
                    "lease_expired": True,
                }
            ]
        )
        calls: list[tuple[list[Any], list[Any], list[Any]]] = []

        async def _record(
            entity_ids: list[Any],
            seed_ids: list[Any],
            created_ids: list[Any],
            _vector_work: VectorWork,
        ) -> list[StageFailure]:
            calls.append((entity_ids, seed_ids, created_ids))
            return []

        handled = await resume_incomplete_jobs(store, roll_forward=_record)

        assert handled == [job_id]
        assert calls == [([affected], [seed], [created])]
        assert store.jobs[job_id]["status"] == "done"

    async def test_roll_forward_failure_leaves_job_cleaning(self) -> None:
        """A cleanup that returns a failure is retried, not marked done."""
        job_id = str(uuid4())
        store = _FakeResumeStore(
            [
                {
                    "id": job_id,
                    "status": "committed",
                    "affected_entity_ids": [],
                    "component_seed_ids": [str(uuid4())],
                    "created_entity_ids": [],
                    "lease_expired": True,
                }
            ]
        )

        async def _fail(
            entity_ids: list[Any],
            seed_ids: list[Any],
            created_ids: list[Any],
            _vector_work: VectorWork,
        ) -> list[StageFailure]:
            return [
                StageFailure(
                    item_id=str(seed_ids[0]),
                    error_type="RuntimeError",
                    error_message="rebuild failed",
                )
            ]

        await resume_incomplete_jobs(store, roll_forward=_fail)

        assert store.jobs[job_id]["status"] == "cleaning"

    async def test_add_job_with_only_seeds_still_runs_cleanup(self) -> None:
        """A job with no affected entities replays when it recorded components.

        An add never has an affected-entity snapshot, so its seeds are the
        only work its cleanup has.
        """
        job_id = str(uuid4())
        seed = uuid4()
        store = _FakeResumeStore(
            [
                {
                    "id": job_id,
                    "status": "committed",
                    "affected_entity_ids": [],
                    "component_seed_ids": [str(seed)],
                    "lease_expired": True,
                }
            ]
        )
        calls: list[tuple[list[Any], list[Any]]] = []

        async def _record(
            entity_ids: list[Any],
            seed_ids: list[Any],
            created_ids: list[Any],
            _vector_work: VectorWork,
        ) -> None:
            calls.append((entity_ids, seed_ids))

        handled = await resume_incomplete_jobs(store, roll_forward=_record)

        assert handled == [job_id]
        assert calls == [([], [seed])]

    async def test_seed_cleanup_failure_leaves_the_job_cleaning(self) -> None:
        """A failed rebuild keeps the job in cleaning so a later open retries it."""
        job_id = str(uuid4())
        store = _FakeResumeStore(
            [
                {
                    "id": job_id,
                    "status": "committed",
                    "affected_entity_ids": [],
                    "component_seed_ids": [str(uuid4())],
                    "lease_expired": True,
                }
            ]
        )

        async def _failing(
            entity_ids: list[Any],
            seed_ids: list[Any],
            created_ids: list[Any],
            _vector_work: VectorWork,
        ) -> None:
            raise RuntimeError("rebuild blew up")

        handled = await resume_incomplete_jobs(store, roll_forward=_failing)

        assert handled == []
        assert store.jobs[job_id]["status"] == "cleaning"

    async def test_job_with_seeds_is_not_finished_without_cleanup(self) -> None:
        """Without a cleanup callable, a job that has work left stays cleaning."""
        job_id = str(uuid4())
        store = _FakeResumeStore(
            [
                {
                    "id": job_id,
                    "status": "committed",
                    "affected_entity_ids": [],
                    "component_seed_ids": [str(uuid4())],
                    "lease_expired": True,
                }
            ]
        )

        handled = await resume_incomplete_jobs(store)

        assert handled == []
        assert store.jobs[job_id]["status"] == "cleaning"

    async def test_job_without_work_skips_cleanup(self) -> None:
        """A job that recorded neither list finishes without calling cleanup."""
        job_id = str(uuid4())
        store = _FakeResumeStore(
            [
                {
                    "id": job_id,
                    "status": "committed",
                    "affected_entity_ids": [],
                    "component_seed_ids": [],
                    "lease_expired": True,
                }
            ]
        )
        calls: list[object] = []

        async def _record(
            entity_ids: list[Any],
            seed_ids: list[Any],
            created_ids: list[Any],
            _vector_work: VectorWork,
        ) -> None:
            calls.append((entity_ids, seed_ids))

        handled = await resume_incomplete_jobs(store, roll_forward=_record)

        assert handled == [job_id]
        assert calls == []

    async def test_committed_job_prune_failure_leaves_it_cleaning(self) -> None:
        """A pruning failure leaves the job claimed but not finished.

        A later open must retry the cleanup, so the job cannot reach its
        terminal state until pruning actually succeeds.
        """
        job_id = str(uuid4())
        store = _FakeResumeStore(
            [
                {
                    "id": job_id,
                    "status": "committed",
                    "affected_entity_ids": [str(uuid4())],
                    "lease_expired": True,
                }
            ]
        )

        async def _failing_prune(
            entity_ids: list[Any],
            seed_ids: list[Any],
            created_ids: list[Any],
            _vector_work: VectorWork,
        ) -> None:
            raise RuntimeError("prune blew up")

        handled = await resume_incomplete_jobs(store, roll_forward=_failing_prune)

        assert handled == []
        assert store.jobs[job_id]["status"] == "cleaning"

    async def test_committed_job_renews_while_pruning(self) -> None:
        """Recovery keeps its lease live until slow cleanup reaches done."""
        job_id = str(uuid4())
        store = _FakeResumeStore(
            [
                {
                    "id": job_id,
                    "status": "committed",
                    "affected_entity_ids": [str(uuid4())],
                    "lease_expired": True,
                }
            ]
        )

        async def _slow_prune(
            entity_ids: list[Any],
            seed_ids: list[Any],
            created_ids: list[Any],
            _vector_work: VectorWork,
        ) -> None:
            await asyncio.sleep(1.1)

        handled = await resume_incomplete_jobs(
            store, roll_forward=_slow_prune, lease_ttl_seconds=1
        )

        assert handled == [job_id]
        assert store.jobs[job_id]["status"] == "done"
        assert store.renewal_count > 0

    async def test_done_transition_does_not_cancel_recovery(self) -> None:
        """A renewal ending during the done transition leaves recovery successful."""
        job_id = str(uuid4())
        store = _FakeResumeStore(
            [
                {
                    "id": job_id,
                    "status": "committed",
                    "affected_entity_ids": [],
                    "lease_expired": True,
                }
            ]
        )
        store.finish_delay_seconds = 0.5

        handled = await asyncio.wait_for(
            resume_incomplete_jobs(store, lease_ttl_seconds=1), timeout=2
        )

        assert handled == [job_id]
        assert store.jobs[job_id]["status"] == "done"

    async def test_failed_finish_is_not_reported_recovered(self) -> None:
        """A claim whose terminal write fails remains eligible for another open."""
        job_id = str(uuid4())
        store = _FakeResumeStore(
            [
                {
                    "id": job_id,
                    "status": "committed",
                    "affected_entity_ids": [],
                    "lease_expired": True,
                }
            ]
        )
        store.finish_allowed = False

        handled = await resume_incomplete_jobs(store)

        assert handled == []
        assert store.jobs[job_id]["status"] == "cleaning"
