"""Cutover Job lease contention against a real Neo4j instance.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``). The ``skipif``
only guards the missing extra; with the extra installed the tests expect a
reachable Neo4j at the default ``NEO4J_URI``.
"""

import asyncio
import importlib.util
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from agrag.common.data_models.cutover_job import CUTOVER_JOB_LABEL
from agrag.cypher.cutover_job_read import find_incomplete_jobs_query
from agrag.cypher.cutover_job_write import (
    acquire_lease_query,
    claim_pending_job_query,
    clear_pending_tag_query,
    commit_job_query,
    finish_cleaning_query,
    renew_lease_query,
    rollback_claimed_job_query,
    rollback_job_query,
    start_cleaning_query,
)
from agrag.cypher.schema import cutover_job_document_key_constraint_query
from agrag.graphdb import build_graph_store
from agrag.ingestion._cutover import run_cutover_job
from agrag.ingestion._resume import resume_incomplete_jobs
from agrag.ingestion.settings import CutoverJobSettings


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _FakeRenewBeforePendingClaimStore:
    """Makes a scanned pending job live just before recovery claims it."""

    def __init__(self, store: Any, job_id: str) -> None:
        """Wrap a store and target one pending job."""
        self.store = store
        self.job_id = job_id
        self.renewed = False

    async def execute_read(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Delegate reads without changing the scanned result."""
        return await self.store.execute_read(query, parameters)

    async def execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Renew the target immediately before recovery's pending claim."""
        if query == claim_pending_job_query() and not self.renewed:
            self.renewed = True
            await self.store.execute_write(
                "MATCH (job:CutoverJob {id: $job_id}) "
                "SET job.lease_expires_at = datetime($lease_expires_at)",
                {
                    "job_id": self.job_id,
                    "lease_expires_at": (
                        datetime.now(UTC) + timedelta(seconds=60)
                    ).isoformat(),
                },
            )
        return await self.store.execute_write(query, parameters)


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestCutoverJobConcurrency:
    """Concurrent lease acquisition against real Neo4j."""

    async def test_simultaneous_acquire_yields_one_winner(self) -> None:
        """Two racers for one key converge to a single winner.

        Both ``MERGE`` on the same ``document_key`` under the uniqueness
        constraint: exactly one claimant gets back its own token, with no
        constraint violation surfacing to either caller.
        """
        store = build_graph_store("neo4j")
        await store.connect()
        key = f"cutover-concurrency-{uuid4().hex}"
        try:
            await store.execute_write(cutover_job_document_key_constraint_query())
            tokens = [str(uuid4()), str(uuid4())]

            async def acquire(token: str) -> list[dict[str, Any]]:
                expires = datetime.now(UTC) + timedelta(seconds=60)
                return await store.execute_write(
                    acquire_lease_query(),
                    {
                        "job_id": str(uuid4()),
                        "document_key": key,
                        "verb": "add",
                        "lease_token": token,
                        "lease_expires_at": expires.isoformat(),
                        "affected_entity_ids": [],
                        "created_at": datetime.now(UTC).isoformat(),
                    },
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
        finally:
            await store.execute_write(
                "MATCH (job:CutoverJob {document_key: $key}) DETACH DELETE job",
                {"key": key},
            )
            await store.close()


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestCutoverJobLeaseLifetime:
    """A live job keeps an unexpired lease through every phase."""

    async def test_expired_lease_cannot_be_renewed(self) -> None:
        """A worker cannot revive its own lease after it expires."""
        store = build_graph_store("neo4j")
        await store.connect()
        key = f"cutover-expired-renewal-{uuid4().hex}"
        job_id = str(uuid4())
        token = str(uuid4())
        try:
            await store.execute_write(cutover_job_document_key_constraint_query())
            await store.execute_write(
                acquire_lease_query(),
                {
                    "job_id": job_id,
                    "document_key": key,
                    "verb": "add",
                    "lease_token": token,
                    "lease_expires_at": (
                        datetime.now(UTC) - timedelta(seconds=1)
                    ).isoformat(),
                    "affected_entity_ids": [],
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )

            renewed = await store.execute_write(
                renew_lease_query(),
                {
                    "job_id": job_id,
                    "lease_token": token,
                    "lease_expires_at": (
                        datetime.now(UTC) + timedelta(seconds=300)
                    ).isoformat(),
                },
            )

            assert renewed == []
        finally:
            await store.execute_write(
                "MATCH (job:CutoverJob {document_key: $key}) DETACH DELETE job",
                {"key": key},
            )
            await store.close()

    @pytest.mark.parametrize(
        ("status", "transition"),
        [
            ("pending", commit_job_query()),
            ("committed", start_cleaning_query()),
            ("cleaning", finish_cleaning_query()),
        ],
    )
    async def test_expired_lease_cannot_advance_phase(
        self, status: str, transition: str
    ) -> None:
        """A worker cannot advance any phase after its lease expires."""
        store = build_graph_store("neo4j")
        await store.connect()
        key = f"cutover-expired-transition-{uuid4().hex}"
        job_id = str(uuid4())
        token = str(uuid4())
        try:
            await store.execute_write(cutover_job_document_key_constraint_query())
            await store.execute_write(
                acquire_lease_query(),
                {
                    "job_id": job_id,
                    "document_key": key,
                    "verb": "add",
                    "lease_token": token,
                    "lease_expires_at": (
                        datetime.now(UTC) - timedelta(seconds=1)
                    ).isoformat(),
                    "affected_entity_ids": [],
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )
            await store.execute_write(
                "MATCH (job:CutoverJob {id: $job_id}) SET job.status = $status",
                {"job_id": job_id, "status": status},
            )

            transitioned = await store.execute_write(
                transition, {"job_id": job_id, "lease_token": token}
            )

            assert transitioned == []
        finally:
            await store.execute_write(
                "MATCH (job:CutoverJob {document_key: $key}) DETACH DELETE job",
                {"key": key},
            )
            await store.close()

    async def test_recovery_renews_lease_during_slow_cleanup(self) -> None:
        """Recovery can finish cleanup that outlasts its initial lease."""
        store = build_graph_store("neo4j")
        await store.connect()
        key = f"cutover-slow-recovery-{uuid4().hex}"
        job_id = str(uuid4())
        token = str(uuid4())
        affected_entity_id = str(uuid4())
        prune_ran = False
        try:
            await store.execute_write(cutover_job_document_key_constraint_query())
            await store.execute_write(
                acquire_lease_query(),
                {
                    "job_id": job_id,
                    "document_key": key,
                    "verb": "add",
                    "lease_token": token,
                    "lease_expires_at": (
                        datetime.now(UTC) + timedelta(seconds=300)
                    ).isoformat(),
                    "affected_entity_ids": [affected_entity_id],
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )
            assert await store.execute_write(
                commit_job_query(), {"job_id": job_id, "lease_token": token}
            )
            await store.execute_write(
                "MATCH (job:CutoverJob {id: $job_id}) "
                "SET job.lease_expires_at = datetime($lease_expires_at)",
                {
                    "job_id": job_id,
                    "lease_expires_at": (
                        datetime.now(UTC) - timedelta(seconds=1)
                    ).isoformat(),
                },
            )

            async def slow_prune(_: list[object]) -> None:
                nonlocal prune_ran
                prune_ran = True
                await asyncio.sleep(1.1)

            recovered = await resume_incomplete_jobs(
                store, roll_forward=slow_prune, lease_ttl_seconds=1
            )
            rows = await store.execute_read(
                "MATCH (job:CutoverJob {id: $job_id}) RETURN job.status AS status",
                {"job_id": job_id},
            )

            assert recovered == [job_id]
            assert rows == [{"status": "done"}]
            assert prune_ran
        finally:
            await store.execute_write(
                "MATCH (job:CutoverJob {document_key: $key}) DETACH DELETE job",
                {"key": key},
            )
            await store.close()

    async def test_recovery_does_not_rollback_a_pending_job_renewed_after_scan(
        self,
    ) -> None:
        """Recovery fences a stale expiry result before deleting pending writes."""
        store = build_graph_store("neo4j")
        await store.connect()
        key = f"cutover-stale-pending-{uuid4().hex}"
        job_id = str(uuid4())
        token = str(uuid4())
        try:
            await store.execute_write(cutover_job_document_key_constraint_query())
            await store.execute_write(
                acquire_lease_query(),
                {
                    "job_id": job_id,
                    "document_key": key,
                    "verb": "add",
                    "lease_token": token,
                    "lease_expires_at": (
                        datetime.now(UTC) - timedelta(seconds=1)
                    ).isoformat(),
                    "affected_entity_ids": [],
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )
            await store.execute_write(
                "CREATE (:TestCutoverPending {_pending_job_id: $job_id})",
                {"job_id": job_id},
            )
            recovering_store = _FakeRenewBeforePendingClaimStore(store, job_id)

            recovered = await resume_incomplete_jobs(recovering_store)
            job_rows = await store.execute_read(
                "MATCH (job:CutoverJob {id: $job_id}) RETURN job.status AS status",
                {"job_id": job_id},
            )
            pending_rows = await store.execute_read(
                "MATCH (node:TestCutoverPending {_pending_job_id: $job_id}) "
                "RETURN count(node) AS count",
                {"job_id": job_id},
            )

            assert recovering_store.renewed
            assert recovered == []
            assert job_rows == [{"status": "pending"}]
            assert pending_rows == [{"count": 1}]
        finally:
            await store.execute_write(
                "MATCH (node:TestCutoverPending {_pending_job_id: $job_id}) "
                "DETACH DELETE node",
                {"job_id": job_id},
            )
            await store.execute_write(
                "MATCH (job:CutoverJob {document_key: $key}) DETACH DELETE job",
                {"key": key},
            )
            await store.close()

    async def test_cleaning_job_is_not_resumable_while_its_lease_is_live(
        self,
    ) -> None:
        """Entering cleaning must not make the job look abandoned.

        A concurrent ``Graph.open`` resume decides from ``lease_expired``;
        it must read ``False`` for a job that just started cleaning.
        """
        store = build_graph_store("neo4j")
        await store.connect()
        key = f"cutover-cleaning-lease-{uuid4().hex}"
        job_id = str(uuid4())
        token = str(uuid4())
        try:
            await store.execute_write(cutover_job_document_key_constraint_query())
            expires = datetime.now(UTC) + timedelta(seconds=300)
            await store.execute_write(
                acquire_lease_query(),
                {
                    "job_id": job_id,
                    "document_key": key,
                    "verb": "add",
                    "lease_token": token,
                    "lease_expires_at": expires.isoformat(),
                    "affected_entity_ids": [],
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )
            params = {"job_id": job_id, "lease_token": token}
            assert await store.execute_write(commit_job_query(), params)
            assert await store.execute_write(start_cleaning_query(), params)

            rows = await store.execute_read(find_incomplete_jobs_query())
            [row] = [r for r in rows if r["id"] == job_id]
            assert row["status"] == "cleaning"
            assert row["lease_expired"] is False
        finally:
            await store.execute_write(
                "MATCH (job:CutoverJob {document_key: $key}) DETACH DELETE job",
                {"key": key},
            )
            await store.close()

    async def test_slow_job_keeps_its_lease_past_the_ttl(self) -> None:
        """A phase longer than the TTL is not stolen by a concurrent resume."""
        store = build_graph_store("neo4j")
        await store.connect()
        key = f"cutover-slow-{uuid4().hex}"
        seen: dict[str, str] = {}
        resumed: list[str] = []

        async def slow_write(job_id: Any) -> None:
            seen["job_id"] = str(job_id)
            await asyncio.sleep(2.5)
            resumed.extend(await resume_incomplete_jobs(store))

        async def cleanup() -> None:
            return None

        try:
            await store.execute_write(cutover_job_document_key_constraint_query())
            await run_cutover_job(
                verb="add",
                document_key=key,
                affected_entity_ids=[],
                graph_store=store,
                vector_store=None,
                vector_collections=[],
                settings=CutoverJobSettings(lease_ttl_seconds=1),
                pending_write=slow_write,
                cleanup=cleanup,
            )
            assert seen["job_id"] not in resumed
            rows = await store.execute_read(
                "MATCH (job:CutoverJob {document_key: $key}) RETURN job.status AS s",
                {"key": key},
            )
            assert rows == [{"s": "done"}]
        finally:
            await store.execute_write(
                "MATCH (job:CutoverJob {document_key: $key}) DETACH DELETE job",
                {"key": key},
            )
            await store.close()


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestClearPendingTagAndRollbackAgainstRealNeo4j:
    """Tag-clearing and rollback executed against a real Neo4j instance.

    Both queries chain an aggregating ``WITH`` after the node-tag step and
    then match tagged relationships: a relationship match with zero rows
    silently drops the whole result row unless it is optional, which no
    substring-based unit test can catch. These tests seed real tagged data,
    including the zero-tagged-relationship case, and assert against actual
    query execution.
    """

    async def _seed_tagged_graph(self, store: Any, job_id: str) -> None:
        await store.execute_write(
            "CREATE (a:TestCutoverPending {name: 'a', _pending_job_id: $job_id}) "
            "CREATE (b:TestCutoverPending {name: 'b', _pending_job_id: $job_id}) "
            "CREATE (a)-[:TEST_REL {_pending_job_id: $job_id}]->(b) "
            "CREATE (c:TestCutoverPending {name: 'c', _pending_job_id: $job_id})",
            {"job_id": job_id},
        )

    async def test_clear_pending_tag_clears_nodes_and_relationship(self) -> None:
        """Clearing removes the tag from tagged nodes and a tagged edge."""
        store = build_graph_store("neo4j")
        await store.connect()
        job_id = str(uuid4())
        try:
            await self._seed_tagged_graph(store, job_id)
            rows = await store.execute_write(
                clear_pending_tag_query(), {"job_id": job_id}
            )
            assert rows == [{"cleared_nodes": 3, "cleared_relationships": 1}]
            remaining = await store.execute_read(
                "MATCH (n:TestCutoverPending) "
                "WHERE n._pending_job_id IS NOT NULL RETURN count(n) AS c",
                {},
            )
            assert remaining[0]["c"] == 0
        finally:
            await store.execute_write(
                "MATCH (n:TestCutoverPending) DETACH DELETE n", {}
            )
            await store.close()

    async def test_clear_pending_tag_with_no_relationships_still_returns_a_row(
        self,
    ) -> None:
        """Clearing with zero tagged relationships still reports node count."""
        store = build_graph_store("neo4j")
        await store.connect()
        job_id = str(uuid4())
        try:
            await store.execute_write(
                "CREATE (a:TestCutoverPending {name: 'a', _pending_job_id: $job_id})",
                {"job_id": job_id},
            )
            rows = await store.execute_write(
                clear_pending_tag_query(), {"job_id": job_id}
            )
            assert rows == [{"cleared_nodes": 1, "cleared_relationships": 0}]
        finally:
            await store.execute_write(
                "MATCH (n:TestCutoverPending) DETACH DELETE n", {}
            )
            await store.close()

    async def test_rollback_with_no_relationships_still_deletes_the_job_node(
        self,
    ) -> None:
        """Rollback deletes the job node even when no relationship is tagged."""
        store = build_graph_store("neo4j")
        await store.connect()
        job_id = str(uuid4())
        try:
            await store.execute_write(
                f"CREATE (job:{CUTOVER_JOB_LABEL} {{id: $job_id, document_key: $key}}) "
                "CREATE (a:TestCutoverPending {name: 'a', _pending_job_id: $job_id})",
                {"job_id": job_id, "key": f"rollback-test-{job_id}"},
            )
            rows = await store.execute_write(rollback_job_query(), {"job_id": job_id})
            assert rows == [{"deleted_nodes": 1, "deleted_relationships": 0}]
            job_left = await store.execute_read(
                f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) RETURN job",
                {"job_id": job_id},
            )
            assert job_left == []
        finally:
            await store.execute_write(
                "MATCH (n:TestCutoverPending) DETACH DELETE n", {}
            )
            await store.execute_write(
                f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) DETACH DELETE job",
                {"job_id": job_id},
            )
            await store.close()

    async def test_claimed_rollback_with_no_pending_data_still_deletes_the_job_node(
        self,
    ) -> None:
        """A claimed rollback releases a lease before a pending write starts."""
        store = build_graph_store("neo4j")
        await store.connect()
        job_id = str(uuid4())
        token = str(uuid4())
        try:
            await store.execute_write(
                f"CREATE (job:{CUTOVER_JOB_LABEL} {{"
                "id: $job_id, document_key: $key, status: 'pending', "
                "lease_token: $token, lease_expires_at: datetime($lease_expires_at)})",
                {
                    "job_id": job_id,
                    "key": f"rollback-empty-test-{job_id}",
                    "token": token,
                    "lease_expires_at": (
                        datetime.now(UTC) + timedelta(seconds=60)
                    ).isoformat(),
                },
            )
            rows = await store.execute_write(
                rollback_claimed_job_query(),
                {"job_id": job_id, "lease_token": token},
            )
            assert rows == [{"deleted_nodes": 0, "deleted_relationships": 0}]
            job_left = await store.execute_read(
                f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) RETURN job",
                {"job_id": job_id},
            )
            assert job_left == []
        finally:
            await store.execute_write(
                f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) DETACH DELETE job",
                {"job_id": job_id},
            )
            await store.close()
