"""Tests for the Graph.open() resume hook against a scripted store fake.

The fake implements find_incomplete_jobs_query/claim_job_query/
rollback_job_query/finish_cleaning_query's contracts, mirroring the fake
in test_cutover.py, so these tests prove resume_incomplete_jobs's own
orchestration (which jobs it skips, rolls back, or rolls forward) rather
than any one query's text.
"""

from typing import Any
from uuid import uuid4

from agrag.cypher.cutover_job_write import (
    claim_job_query,
    finish_cleaning_query,
    rollback_job_query,
)
from agrag.ingestion._resume import resume_incomplete_jobs


class _FakeResumeStore:
    """In-memory stand-in exposing the queries resume_incomplete_jobs uses."""

    def __init__(self, jobs: list[dict[str, Any]]) -> None:
        """Seed the fake with the incomplete-job rows a read would return.

        Args:
            jobs: Each row as find_incomplete_jobs_query would shape it:
                id, status, affected_entity_ids, lease_expired.
        """
        self.jobs = {
            job["id"]: {**job, "lease_token": job.get("lease_token", str(uuid4()))}
            for job in jobs
        }

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
        if query == rollback_job_query():
            self.jobs.pop(job_id, None)
            return [{"deleted_nodes": 0, "deleted_relationships": 0}]
        if query == claim_job_query():
            job = self.jobs.get(job_id)
            if job is None or job["status"] not in ("committed", "cleaning"):
                return []
            job["status"] = "cleaning"
            job["lease_token"] = str(params["lease_token"])
            return [{"status": job["status"]}]
        if query == finish_cleaning_query():
            job = self.jobs.get(job_id)
            if job is None or job["lease_token"] != str(params["lease_token"]):
                return []
            job["status"] = "done"
            return [{"id": job_id}]
        raise AssertionError(f"unexpected query: {query!r}")


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

    async def test_committed_job_rolls_forward_to_done(self) -> None:
        """A committed job's cleanup finishes and it reaches the done state."""
        job_id = str(uuid4())
        store = _FakeResumeStore(
            [
                {
                    "id": job_id,
                    "status": "committed",
                    "affected_entity_ids": [],
                    "lease_expired": False,
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
                    "lease_expired": False,
                }
            ]
        )

        async def _failing_prune(entity_ids: list[Any]) -> None:
            raise RuntimeError("prune blew up")

        handled = await resume_incomplete_jobs(store, roll_forward=_failing_prune)

        assert handled == [job_id]
        assert store.jobs[job_id]["status"] == "cleaning"
