"""Tests for the Graph.open() resume hook against a scripted store fake.

The fake implements find_incomplete_jobs_query, both recovery claims,
rollback_claimed_job_query, and finish_cleaning_query, mirroring the fake in
test_cutover.py. These tests prove resume_incomplete_jobs's orchestration
(which jobs it skips, rolls back, or rolls forward) rather than any one
query's text.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from agrag.cypher.cutover_job_write import (
    claim_job_query,
    claim_pending_job_query,
    finish_cleaning_query,
    renew_lease_query,
    rollback_claimed_job_query,
)
from agrag.ingestion._resume import resume_incomplete_jobs


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

    async def execute_read(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Return every still-incomplete job's row."""
        return [
            dict(job)
            for job in self.jobs.values()
            if job["status"] in ("pending", "committed", "cleaning")
        ]

    async def execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Dispatch one resume-phase query against the in-memory job table."""
        params = parameters or {}
        job_id = str(params.get("job_id"))
        if query == rollback_claimed_job_query():
            return self._rollback_claimed(job_id, params)
        if query == claim_job_query():
            return self._claim(job_id, params)
        if query == claim_pending_job_query():
            return self._claim_pending(job_id, params)
        if query == renew_lease_query():
            return self._renew(job_id, params)
        if query == finish_cleaning_query():
            rows = self._finish(job_id, params)
            if self.finish_delay_seconds:
                await asyncio.sleep(self.finish_delay_seconds)
            return rows
        raise AssertionError(f"unexpected query: {query!r}")

    def _claim(self, job_id: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Claim one committed or cleaning job for recovery."""
        job = self.jobs.get(job_id)
        if job is None or job["status"] not in ("committed", "cleaning"):
            return []
        job["status"] = "cleaning"
        job["lease_token"] = str(params["lease_token"])
        job["lease_expires_at"] = datetime.fromisoformat(
            str(params["lease_expires_at"])
        )
        return [{"status": job["status"]}]

    def _claim_pending(
        self, job_id: str, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Claim one lapsed pending job before deleting its staged writes."""
        job = self.jobs.get(job_id)
        if job is None:
            return []
        if self.renew_before_pending_claim:
            job["lease_expired"] = False
        if (
            job["status"] != "pending"
            or not job["lease_expired"]
            or job["lease_token"] != str(params["expected_lease_token"])
        ):
            return []
        job["lease_token"] = str(params["lease_token"])
        job["lease_expires_at"] = datetime.fromisoformat(
            str(params["lease_expires_at"])
        )
        job["lease_expired"] = False
        return [{"id": job_id}]

    def _rollback_claimed(
        self, job_id: str, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Delete only a pending job held by the recovery claimant."""
        job = self.jobs.get(job_id)
        if (
            job is None
            or job["status"] != "pending"
            or job["lease_token"] != str(params["lease_token"])
        ):
            return []
        self.rollback_count += 1
        self.jobs.pop(job_id)
        return [{"deleted_nodes": 0, "deleted_relationships": 0}]

    def _renew(self, job_id: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Renew one active recovery claim while it remains live."""
        job = self.jobs.get(job_id)
        if (
            job is None
            or job["lease_token"] != str(params["lease_token"])
            or job["status"] not in ("pending", "committed", "cleaning")
            or job["lease_expires_at"] < datetime.now(UTC)
        ):
            return []
        job["lease_expires_at"] = datetime.fromisoformat(
            str(params["lease_expires_at"])
        )
        self.renewal_count += 1
        return [{"id": job_id}]

    def _finish(self, job_id: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Mark one live recovery claim done when its cleanup completes."""
        job = self.jobs.get(job_id)
        if (
            job is None
            or not self.finish_allowed
            or job["lease_token"] != str(params["lease_token"])
            or job["lease_expires_at"] < datetime.now(UTC)
        ):
            return []
        job["status"] = "done"
        return [{"id": job_id}]


class TestResumeIncompleteJobs:
    """resume_incomplete_jobs rolls back or forward, per job status."""

    async def test_pending_job_with_lapsed_lease_is_rolled_back(self) -> None:
        """A pending job whose lease expired is deleted, not left behind."""
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

        handled = await resume_incomplete_jobs(store)

        assert handled == [job_id]
        assert job_id not in store.jobs

    async def test_pending_job_with_live_lease_is_left_alone(self) -> None:
        """A pending job whose worker may still be running is skipped."""
        job_id = str(uuid4())
        store = _FakeResumeStore(
            [
                {
                    "id": job_id,
                    "status": "pending",
                    "affected_entity_ids": [],
                    "lease_expired": False,
                }
            ]
        )

        handled = await resume_incomplete_jobs(store)

        assert handled == []
        assert store.jobs[job_id]["status"] == "pending"

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

    async def test_committed_job_rolls_forward_to_done(self) -> None:
        """A committed job's cleanup finishes and it reaches the done state."""
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

        handled = await resume_incomplete_jobs(store)

        assert handled == [job_id]
        assert store.jobs[job_id]["status"] == "done"

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

        async def _failing_prune(entity_ids: list[Any]) -> None:
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

        async def _slow_prune(entity_ids: list[Any]) -> None:
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
