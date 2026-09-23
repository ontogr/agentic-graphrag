"""Tests for the Cutover Job lease protocol against a scripted store.

The fake below implements the exact semantics each query builder's
docstring promises — atomic MERGE on document_key, compare-and-swap on
the fencing token, expiry comparison on the lease — so these tests prove
the protocol's contention properties, not any one query's text. The fake
performs no awaits between check and write, mirroring the
constraint-backed atomicity the real database provides. Real MERGE and
constraint behavior under concurrency is covered by the integration test
instead.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from agrag.cypher.cutover_job_write import (
    acquire_lease_query,
    commit_job_query,
    steal_expired_lease_query,
)
from agrag.ingestion.settings import CutoverJobSettings


class _FakeCutoverStore:
    """In-memory stand-in implementing the lease queries' contracts."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}

    async def execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run one lease query against the in-memory job table."""
        params = parameters or {}
        if query == acquire_lease_query():
            return self._acquire(params)
        if query == steal_expired_lease_query():
            return self._steal(params)
        if query == commit_job_query():
            return self._commit(params)
        raise AssertionError(f"unexpected query: {query!r}")

    def _acquire(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        key = str(params["document_key"])
        job = self._jobs.get(key)
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
            self._jobs[key] = job
        return [{"lease_token": job["lease_token"], "status": job["status"]}]

    def _steal(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        job = self._jobs.get(str(params["document_key"]))
        if job is None:
            return []
        expired = job["lease_expires_at"] < datetime.now(UTC)
        if job["status"] in ("done", "rolled_back") or (
            job["status"] == "pending" and expired
        ):
            job["status"] = "pending"
            job["verb"] = params["verb"]
            job["lease_token"] = str(params["lease_token"])
            job["lease_expires_at"] = datetime.fromisoformat(
                str(params["lease_expires_at"])
            )
            return [{"lease_token": job["lease_token"]}]
        return []

    def _commit(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        for job in self._jobs.values():
            if (
                job["id"] == str(params["job_id"])
                and job["lease_token"] == str(params["lease_token"])
                and job["status"] == "pending"
            ):
                job["status"] = "committed"
                return [{"id": job["id"]}]
        return []

    def expire(self, document_key: str) -> None:
        """Force a job's lease into the past, simulating a dead worker."""
        self._jobs[document_key]["lease_expires_at"] = datetime.now(UTC) - timedelta(
            seconds=1
        )


def _acquire_params(document_key: str, token: str, expires: datetime) -> dict[str, Any]:
    """Build acquire_lease_query parameters for one claimant."""
    return {
        "job_id": str(uuid4()),
        "document_key": document_key,
        "verb": "add",
        "lease_token": token,
        "lease_expires_at": expires.isoformat(),
        "affected_entity_ids": [],
        "created_at": datetime.now(UTC).isoformat(),
    }


class TestCutoverJobLease:
    """Lease contention and fencing behavior."""

    async def test_single_acquirer_wins_the_lease(self) -> None:
        """The first claimant gets back its own token."""
        store = _FakeCutoverStore()
        settings = CutoverJobSettings()
        token = str(uuid4())
        expires = datetime.now(UTC) + timedelta(seconds=settings.lease_ttl_seconds)
        rows = await store.execute_write(
            acquire_lease_query(), _acquire_params("doc", token, expires)
        )
        assert rows == [{"lease_token": token, "status": "pending"}]

    async def test_second_acquirer_loses_while_lease_live(self) -> None:
        """A live lease makes the latecomer see the holder's token."""
        store = _FakeCutoverStore()
        settings = CutoverJobSettings()
        expires = datetime.now(UTC) + timedelta(seconds=settings.lease_ttl_seconds)
        first_token, second_token = str(uuid4()), str(uuid4())
        await store.execute_write(
            acquire_lease_query(), _acquire_params("doc", first_token, expires)
        )
        rows = await store.execute_write(
            acquire_lease_query(), _acquire_params("doc", second_token, expires)
        )
        assert rows == [{"lease_token": first_token, "status": "pending"}]

    async def test_concurrent_acquirers_yield_one_winner(self) -> None:
        """Two simultaneous acquirers converge on a single winner."""
        store = _FakeCutoverStore()
        settings = CutoverJobSettings()
        expires = datetime.now(UTC) + timedelta(seconds=settings.lease_ttl_seconds)
        tokens = [str(uuid4()), str(uuid4())]

        async def acquire(token: str) -> list[dict[str, Any]]:
            return await store.execute_write(
                acquire_lease_query(), _acquire_params("doc", token, expires)
            )

        first_rows, second_rows = await asyncio.gather(
            acquire(tokens[0]), acquire(tokens[1])
        )
        winners = [
            token
            for token, rows in zip(tokens, (first_rows, second_rows), strict=True)
            if rows and rows[0]["lease_token"] == token
        ]
        assert len(winners) == 1

    async def test_stale_token_commit_is_rejected(self) -> None:
        """A worker that lost its lease cannot complete a stale commit."""
        store = _FakeCutoverStore()
        settings = CutoverJobSettings()
        expires = datetime.now(UTC) + timedelta(seconds=settings.lease_ttl_seconds)
        key = "doc"
        first_token, second_token = str(uuid4()), str(uuid4())
        first_params = _acquire_params(key, first_token, expires)
        await store.execute_write(acquire_lease_query(), first_params)
        store.expire(key)
        stolen = await store.execute_write(
            steal_expired_lease_query(),
            {
                "document_key": key,
                "verb": "add",
                "lease_token": second_token,
                "lease_expires_at": expires.isoformat(),
            },
        )
        assert stolen == [{"lease_token": second_token}]
        stale_commit = await store.execute_write(
            commit_job_query(),
            {"job_id": first_params["job_id"], "lease_token": first_token},
        )
        assert stale_commit == []

    async def test_live_lease_is_not_stealable(self) -> None:
        """Steal returns no row while the holder's lease is live."""
        store = _FakeCutoverStore()
        settings = CutoverJobSettings()
        expires = datetime.now(UTC) + timedelta(seconds=settings.lease_ttl_seconds)
        await store.execute_write(
            acquire_lease_query(), _acquire_params("doc", str(uuid4()), expires)
        )
        rows = await store.execute_write(
            steal_expired_lease_query(),
            {
                "document_key": "doc",
                "verb": "add",
                "lease_token": str(uuid4()),
                "lease_expires_at": expires.isoformat(),
            },
        )
        assert rows == []

    async def test_terminal_job_is_reusable(self) -> None:
        """A finished job's node is reset for the next job on that key."""
        store = _FakeCutoverStore()
        settings = CutoverJobSettings()
        expires = datetime.now(UTC) + timedelta(seconds=settings.lease_ttl_seconds)
        key = "doc"
        await store.execute_write(
            acquire_lease_query(), _acquire_params(key, str(uuid4()), expires)
        )
        store._jobs[key]["status"] = "done"
        token = str(uuid4())
        rows = await store.execute_write(
            steal_expired_lease_query(),
            {
                "document_key": key,
                "verb": "update",
                "lease_token": token,
                "lease_expires_at": expires.isoformat(),
            },
        )
        assert rows == [{"lease_token": token}]
        assert store._jobs[key]["status"] == "pending"
