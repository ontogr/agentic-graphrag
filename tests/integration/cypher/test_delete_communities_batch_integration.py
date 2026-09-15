"""Integration tests for delete_all_communities batching against real Neo4j.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``). The
``skipif`` only guards the missing extra; with the extra installed the
tests expect a reachable Neo4j at the default ``NEO4J_URI``.
"""

import importlib.util
from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.community import COMMUNITY_LABEL, MEMBER_OF_RELATION
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.cypher.entities import validate_identifier
from agrag.graphdb import build_graph_store
from agrag.ingestion.community import delete_all_communities


neo4j_missing = importlib.util.find_spec("neo4j") is None


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
@pytest.mark.xdist_group(name="community_label")
class TestDeleteCommunitiesBatchIntegration:
    """``delete_all_communities`` batches deletes correctly.

    ``delete_all_communities`` deletes every ``Community`` node in the
    database by design (see agrag.ingestion.graph.Graph.detect_communities's
    full-recompute callers), so this class shares an ``xdist_group`` with
    ``TestCommunitiesForEntitiesOverlapIntegration`` to keep both off
    separate parallel workers -- otherwise this test's delete can wipe the
    other test's Community nodes mid-run.
    """

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Set up a fresh store with a unique entity label.

        ``community_ids`` starts empty and the test fills it in once it
        creates its own Community nodes, so teardown can delete exactly
        those nodes by id instead of the shared ``Community`` label --
        other integration tests write ``Community`` nodes to the same
        database and may be running concurrently.
        """
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        self.entity_label = validate_identifier(f"Entity_{uuid4().hex[:8]}")
        self.community_ids: list[UUID] = []
        yield
        await self.store.execute_write(f"MATCH (n:{self.entity_label}) DETACH DELETE n")
        if self.community_ids:
            await self.store.execute_write(
                "MATCH (n:Community) WHERE n.id IN $ids DETACH DELETE n",
                {"ids": [str(cid) for cid in self.community_ids]},
            )
        await self.store.close()

    async def test_delete_communities_batch_real(self) -> None:
        """Writes 3 Community + MEMBER_OF, deletes with batch_size=2.

        Asserts every batch deletes at most ``batch_size`` nodes, at least
        two batches ran, and this test's own communities are gone
        afterward. Counts are scoped to this test's own community ids
        since ``Community`` is a label shared with concurrently-running
        integration tests against the same database.
        """
        community_ids = [uuid4() for _ in range(3)]
        self.community_ids = community_ids
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

            # Ensure this test's 3 communities exist before delete.
            before = await self.store.execute_read(
                "MATCH (n:Community) WHERE n.id IN $ids RETURN count(n) AS c",
                {"ids": [str(cid) for cid in community_ids]},
            )
            assert before[0]["c"] == 3

            deleted_counts: list[int] = []
            original_write = self.store.execute_write

            async def counting_write(query, parameters=None, **kw):  # type: ignore[no-untyped-def]
                rows = await original_write(query, parameters, **kw)
                if rows and "deleted" in rows[0]:
                    deleted_counts.append(rows[0]["deleted"])
                return rows

            self.store.execute_write = counting_write  # type: ignore[method-assign]
            try:
                await delete_all_communities(self.store, batch_size=2)
            finally:
                self.store.execute_write = original_write  # type: ignore[method-assign]

            # delete_all_communities deletes every Community node in the
            # database, not just this test's own, so the batch count
            # depends on however many other nodes exist concurrently.
            # Assert the bounded-batch contract instead of an exact count:
            # each batch deletes at most batch_size rows, and this test's
            # own 3 communities took at least two batches to clear.
            assert len(deleted_counts) >= 2
            assert all(count <= 2 for count in deleted_counts)

            after = await self.store.execute_read(
                "MATCH (n:Community) WHERE n.id IN $ids RETURN count(n) AS c",
                {"ids": [str(cid) for cid in community_ids]},
            )
            assert after[0]["c"] == 0
        finally:
            await self.store.execute_write(
                "MATCH (n:Community) WHERE n.id IN $ids DETACH DELETE n",
                {"ids": [str(cid) for cid in community_ids]},
            )
