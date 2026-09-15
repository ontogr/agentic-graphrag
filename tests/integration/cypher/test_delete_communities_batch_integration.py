"""Integration tests for delete_all_communities batching against real Neo4j.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``). The
``skipif`` only guards the missing extra; with the extra installed the
tests expect a reachable Neo4j at the default ``NEO4J_URI``.
"""

import importlib.util
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest

from agrag.common.data_models.community import COMMUNITY_LABEL, MEMBER_OF_RELATION
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.cypher.entities import validate_identifier
from agrag.graphdb import build_graph_store
from agrag.ingestion.community import delete_all_communities


neo4j_missing = importlib.util.find_spec("neo4j") is None


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestDeleteCommunitiesBatchIntegration:
    """``delete_all_communities`` batches deletes correctly."""

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Set up a fresh store with a unique entity label."""
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        self.entity_label = validate_identifier(f"Entity_{uuid4().hex[:8]}")
        yield
        await self.store.execute_write(f"MATCH (n:{self.entity_label}) DETACH DELETE n")
        await self.store.execute_write("MATCH (n:Community) DETACH DELETE n")
        await self.store.close()

    async def test_delete_communities_batch_real(self) -> None:
        """Writes 3 Community + MEMBER_OF, deletes with batch_size=2.

        Asserts 2 ``execute_write`` calls (2 + 1) and final count 0.
        """
        community_ids = [uuid4() for _ in range(3)]
        entity_ids = [uuid4() for _ in range(3)]
        try:
            await self.store.upsert_nodes(
                self.entity_label,
                [
                    NodeRecord(
                        id=eid, labels=[self.entity_label], properties={"name": f"e{i}"}
                    )
                    for i, eid in enumerate(entity_ids)
                ],
            )
            await self.store.upsert_nodes(
                COMMUNITY_LABEL,
                [
                    NodeRecord(
                        id=cid,
                        labels=[COMMUNITY_LABEL],
                        properties={
                            "title": f"c{i}",
                            "summary": "s",
                            "rating": 1.0,
                            "rating_explanation": "r",
                            "findings": [],
                            "member_ids": [],
                            "internal_weight": 1.0,
                            "created_at": "2024-01-01T00:00:00",
                        },
                    )
                    for i, cid in enumerate(community_ids)
                ],
            )
            await self.store.upsert_relations(
                [
                    RelationRecord(
                        id=uuid4(),
                        type=MEMBER_OF_RELATION,
                        start_id=entity_ids[i],
                        end_id=community_ids[i],
                        properties={},
                    )
                    for i in range(3)
                ]
            )

            # Ensure 3 communities exist before delete.
            before = await self.store.execute_read(
                "MATCH (n:Community) RETURN count(n) AS c"
            )
            assert before[0]["c"] == 3

            calls = 0
            original_write = self.store.execute_write

            async def counting_write(query, parameters=None, **kw):  # type: ignore[no-untyped-def]
                nonlocal calls
                calls += 1
                return await original_write(query, parameters, **kw)

            self.store.execute_write = counting_write  # type: ignore[method-assign]
            try:
                await delete_all_communities(self.store, batch_size=2)
            finally:
                self.store.execute_write = original_write  # type: ignore[method-assign]

            assert calls == 2

            after = await self.store.execute_read(
                "MATCH (n:Community) RETURN count(n) AS c"
            )
            assert after[0]["c"] == 0
        finally:
            await self.store.execute_write("MATCH (n:Community) DETACH DELETE n")
