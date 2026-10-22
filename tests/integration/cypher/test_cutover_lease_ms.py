"""Cutover Job lease expiry stored as epoch milliseconds against real Neo4j.

The builders receive lease expiries as integer epoch milliseconds and compare
them with ``timestamp()``. Each case creates its own Cutover Job under a
unique document key and deletes that node afterwards. Set NEO4J_URI to an
isolated test database.
"""

import importlib.util
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from agrag.cypher.cutover_job_read import find_incomplete_jobs_query
from agrag.cypher.cutover_job_write import (
    acquire_lease_query,
    claim_pending_job_query,
    commit_job_query,
    job_status_query,
    renew_lease_query,
)
from agrag.graphdb.base import GraphStore
from tests.integration._backend import build_test_store


pytestmark = pytest.mark.neo4j_only


def _expiry_millis(offset_seconds: int) -> int:
    """Return the epoch milliseconds of now shifted by ``offset_seconds``."""
    moment = datetime.now(UTC) + timedelta(seconds=offset_seconds)
    return int(moment.timestamp() * 1000)


def _acquire_params(
    *, document_key: str, job_id: UUID, token: UUID, expires_at_ms: int
) -> dict[str, object]:
    """Return the parameters of the acquire builder for one claimant."""
    return {
        "job_id": str(job_id),
        "document_key": document_key,
        "verb": "add",
        "lease_token": str(token),
        "lease_expires_at": expires_at_ms,
        "affected_entity_ids": [],
        "created_at": datetime.now(UTC).isoformat(),
    }


@pytest.mark.skipif(
    importlib.util.find_spec("neo4j") is None, reason="neo4j extra not installed"
)
class TestCutoverLeaseMillis:
    """Lease expiry in epoch milliseconds drives every lease transition."""

    @staticmethod
    async def _delete_job(store, document_key: str) -> None:
        """Remove the Cutover Job node this case created."""
        await store.execute_write(
            "MATCH (job:CutoverJob {document_key: $document_key}) DETACH DELETE job",
            {"document_key": document_key},
        )

    async def test_live_lease_is_acquired_and_renewed(self) -> None:
        """A future expiry acquires unexpired and can be renewed by its token."""
        store = build_test_store()
        await store.connect()
        document_key = f"lease-ms-{uuid4().hex}"
        job_id, token = uuid4(), uuid4()
        try:
            acquired = await store.execute_write(
                acquire_lease_query(),
                _acquire_params(
                    document_key=document_key,
                    job_id=job_id,
                    token=token,
                    expires_at_ms=_expiry_millis(300),
                ),
            )
            renewed = await store.execute_write(
                renew_lease_query(),
                {
                    "job_id": str(job_id),
                    "lease_token": str(token),
                    "lease_expires_at": _expiry_millis(600),
                },
            )
        finally:
            await self._delete_job(store, document_key)
            await store.close()

        assert acquired == [
            {
                "id": str(job_id),
                "lease_token": str(token),
                "status": "pending",
                "lease_expired": False,
            }
        ]
        assert renewed == [{"id": str(job_id)}]

    async def test_expired_lease_is_flagged_and_claimed_for_rollback(self) -> None:
        """A past expiry reports lease_expired and lets recovery take the job."""
        store = build_test_store()
        await store.connect()
        document_key = f"lease-ms-{uuid4().hex}"
        dead_job_id, dead_token = uuid4(), uuid4()
        recovery_token = uuid4()
        try:
            await store.execute_write(
                acquire_lease_query(),
                _acquire_params(
                    document_key=document_key,
                    job_id=dead_job_id,
                    token=dead_token,
                    expires_at_ms=_expiry_millis(-60),
                ),
            )
            contender = await store.execute_write(
                acquire_lease_query(),
                _acquire_params(
                    document_key=document_key,
                    job_id=uuid4(),
                    token=uuid4(),
                    expires_at_ms=_expiry_millis(300),
                ),
            )
            incomplete = await store.execute_read(find_incomplete_jobs_query(), {})
            claimed = await store.execute_write(
                claim_pending_job_query(),
                {
                    "job_id": str(dead_job_id),
                    "expected_lease_token": str(dead_token),
                    "lease_token": str(recovery_token),
                    "lease_expires_at": _expiry_millis(300),
                },
            )
            status = await store.execute_read(
                job_status_query(), {"job_id": str(dead_job_id)}
            )
        finally:
            await self._delete_job(store, document_key)
            await store.close()

        assert contender[0]["lease_token"] == str(dead_token)
        assert contender[0]["lease_expired"] is True
        dead_row = [row for row in incomplete if row["id"] == str(dead_job_id)]
        assert [row["lease_expired"] for row in dead_row] == [True]
        assert claimed == [{"id": str(dead_job_id)}]
        assert status[0]["lease_token"] == str(recovery_token)

    @pytest.mark.parametrize(
        ("offset_seconds", "applied"),
        [(-60, False), (300, True)],
        ids=["expired_lease_rejected", "live_lease_applied"],
    )
    async def test_commit_guard_follows_lease_expiry(
        self, offset_seconds: int, applied: bool
    ) -> None:
        """Commit applies only while the lease expiry is still in the future."""
        store = build_test_store()
        await store.connect()
        document_key = f"lease-ms-{uuid4().hex}"
        job_id, token = uuid4(), uuid4()
        try:
            await store.execute_write(
                acquire_lease_query(),
                _acquire_params(
                    document_key=document_key,
                    job_id=job_id,
                    token=token,
                    expires_at_ms=_expiry_millis(offset_seconds),
                ),
            )
            committed = await store.execute_write(
                commit_job_query(),
                {
                    "job_id": str(job_id),
                    "lease_token": str(token),
                    "component_seed_ids": [],
                    "created_entity_ids": [],
                },
            )
            status = await store.execute_read(
                job_status_query(), {"job_id": str(job_id)}
            )
        finally:
            await self._delete_job(store, document_key)
            await store.close()

        assert committed == ([{"id": str(job_id)}] if applied else [])
        assert status[0]["status"] == ("committed" if applied else "pending")


# The datetime-based query texts that the builders replaced. Each is kept
# verbatim so the new builders can be checked against the old decisions on
# the same seeded graph.
LEGACY_ACQUIRE_QUERY = (
    "MERGE (job:CutoverJob {document_key: $document_key}) "
    "ON CREATE SET job.id = $job_id, job.status = 'pending', "
    "job.verb = $verb, job.lease_token = $lease_token, "
    "job.lease_expires_at = datetime($lease_expires_at), "
    "job.affected_entity_ids = $affected_entity_ids, "
    "job.created_at = $created_at "
    "RETURN job.id AS id, job.lease_token AS lease_token, job.status AS status, "
    "job.lease_expires_at < datetime() AS lease_expired"
)
LEGACY_RENEW_QUERY = (
    "MATCH (job:CutoverJob {id: $job_id}) "
    "SET job.lease_token = job.lease_token + '' WITH job "
    "WHERE job.lease_token = $lease_token "
    "AND job.lease_expires_at >= datetime() "
    "AND job.status IN ['pending', 'rolling_back', 'committed', 'cleaning'] "
    "SET job.lease_expires_at = datetime($lease_expires_at) "
    "RETURN job.id AS id"
)
LEGACY_COMMIT_QUERY = (
    "MATCH (job:CutoverJob {id: $job_id}) "
    "SET job.lease_token = job.lease_token + '' WITH job "
    "WHERE job.lease_token = $lease_token "
    "AND job.lease_expires_at >= datetime() "
    "AND job.status = 'pending' "
    "SET job.status = 'committed', "
    "job.component_seed_ids = $component_seed_ids, "
    "job.created_entity_ids = $created_entity_ids "
    "RETURN job.id AS id"
)
LEGACY_CLAIM_PENDING_QUERY = (
    "MATCH (job:CutoverJob {id: $job_id}) "
    "SET job.lease_token = job.lease_token + '' WITH job "
    "WHERE job.status IN ['pending', 'rolling_back'] "
    "AND job.lease_token = $expected_lease_token "
    "AND job.lease_expires_at < datetime() "
    "SET job.status = 'rolling_back', job.lease_token = $lease_token, "
    "job.lease_expires_at = datetime($lease_expires_at) "
    "RETURN job.id AS id"
)
LEGACY_FIND_INCOMPLETE_QUERY = (
    "MATCH (job:CutoverJob) "
    "WHERE job.status IN ['pending', 'rolling_back', 'committed', 'cleaning'] "
    "RETURN job.id AS id, job.status AS status, "
    "job.lease_token AS lease_token, "
    "job.affected_entity_ids AS affected_entity_ids, "
    "job.component_seed_ids AS component_seed_ids, "
    "job.created_entity_ids AS created_entity_ids, "
    "job.lease_expires_at < datetime() AS lease_expired"
)


def _lease_expiry(offset_seconds: int, *, legacy: bool) -> int | str:
    """Return a lease expiry as the legacy ISO string or the epoch milliseconds."""
    moment = datetime.now(UTC) + timedelta(seconds=offset_seconds)
    return moment.isoformat() if legacy else int(moment.timestamp() * 1000)


async def _decide_leases(
    store: GraphStore, *, run: str, offset_seconds: int, legacy: bool
) -> dict[str, object]:
    """Run each lease decision on its own job and report what each returned.

    Every job key starts with ``run`` so the caller can remove them all.
    """

    def expiry(seconds: int) -> int | str:
        return _lease_expiry(seconds, legacy=legacy)

    async def seed(key: str) -> tuple[UUID, UUID]:
        job_id, token = uuid4(), uuid4()
        await store.execute_write(
            LEGACY_ACQUIRE_QUERY if legacy else acquire_lease_query(),
            {
                "job_id": str(job_id),
                "document_key": key,
                "verb": "add",
                "lease_token": str(token),
                "lease_expires_at": expiry(offset_seconds),
                "affected_entity_ids": [],
                "created_at": datetime.now(UTC).isoformat(),
            },
        )
        return job_id, token

    renew_job, renew_token = await seed(f"{run}-renew")
    renewed = await store.execute_write(
        LEGACY_RENEW_QUERY if legacy else renew_lease_query(),
        {
            "job_id": str(renew_job),
            "lease_token": str(renew_token),
            "lease_expires_at": expiry(600),
        },
    )

    commit_job, commit_token = await seed(f"{run}-commit")
    committed = await store.execute_write(
        LEGACY_COMMIT_QUERY if legacy else commit_job_query(),
        {
            "job_id": str(commit_job),
            "lease_token": str(commit_token),
            "component_seed_ids": [],
            "created_entity_ids": [],
        },
    )

    claim_job, claim_token = await seed(f"{run}-claim")
    contender = await store.execute_write(
        LEGACY_ACQUIRE_QUERY if legacy else acquire_lease_query(),
        {
            "job_id": str(uuid4()),
            "document_key": f"{run}-claim",
            "verb": "add",
            "lease_token": str(uuid4()),
            "lease_expires_at": expiry(300),
            "affected_entity_ids": [],
            "created_at": datetime.now(UTC).isoformat(),
        },
    )
    claimed = await store.execute_write(
        LEGACY_CLAIM_PENDING_QUERY if legacy else claim_pending_job_query(),
        {
            "job_id": str(claim_job),
            "expected_lease_token": str(claim_token),
            "lease_token": str(uuid4()),
            "lease_expires_at": expiry(300),
        },
    )

    find_job, _ = await seed(f"{run}-find")
    incomplete = await store.execute_read(
        LEGACY_FIND_INCOMPLETE_QUERY if legacy else find_incomplete_jobs_query(), {}
    )
    find_rows = [row for row in incomplete if row["id"] == str(find_job)]

    return {
        "renew": renewed == [{"id": str(renew_job)}],
        "commit": committed == [{"id": str(commit_job)}],
        "contender_lease_expired": contender[0]["lease_expired"],
        "claim": claimed == [{"id": str(claim_job)}],
        "find_lease_expired": [row["lease_expired"] for row in find_rows],
    }


@pytest.mark.skipif(
    importlib.util.find_spec("neo4j") is None, reason="neo4j extra not installed"
)
class TestLegacyLeaseQueriesAgree:
    """The millisecond builders reach the same lease decisions as the old ones."""

    @pytest.mark.parametrize(
        ("offset_seconds", "expected"),
        [
            (
                300,
                {
                    "renew": True,
                    "commit": True,
                    "contender_lease_expired": False,
                    "claim": False,
                    "find_lease_expired": [False],
                },
            ),
            (
                -60,
                {
                    "renew": False,
                    "commit": False,
                    "contender_lease_expired": True,
                    "claim": True,
                    "find_lease_expired": [True],
                },
            ),
        ],
        ids=["live_lease", "expired_lease"],
    )
    async def test_builders_match_legacy_decisions_on_same_expiry(
        self, offset_seconds: int, expected: dict[str, object]
    ) -> None:
        """Renew, commit, claim, acquire and find decide as the datetime queries did."""
        store = build_test_store()
        await store.connect()
        run = f"lease-ms-{uuid4().hex}"
        try:
            legacy = await _decide_leases(
                store, run=f"{run}-legacy", offset_seconds=offset_seconds, legacy=True
            )
            current = await _decide_leases(
                store,
                run=f"{run}-current",
                offset_seconds=offset_seconds,
                legacy=False,
            )
        finally:
            await store.execute_write(
                "MATCH (job:CutoverJob) WHERE job.document_key STARTS WITH $run "
                "DETACH DELETE job",
                {"run": run},
            )
            await store.close()

        assert current == legacy
        assert current == expected
