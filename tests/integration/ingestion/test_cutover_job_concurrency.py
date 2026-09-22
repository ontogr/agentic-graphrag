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

from agrag.cypher.cutover_job_write import acquire_lease_query
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
