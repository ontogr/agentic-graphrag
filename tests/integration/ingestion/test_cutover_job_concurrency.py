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
from agrag.cypher.cutover_job_write import (
    acquire_lease_query,
    clear_pending_tag_query,
    rollback_job_query,
)
from agrag.cypher.schema import cutover_job_document_key_constraint_query
from agrag.graphdb import build_graph_store


neo4j_missing = importlib.util.find_spec("neo4j") is None


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
