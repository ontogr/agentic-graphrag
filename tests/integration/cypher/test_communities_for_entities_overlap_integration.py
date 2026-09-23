"""Integration tests for communities_for_entities_query against real Neo4j.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``). The
``skipif`` only guards the missing extra; with the extra installed the
tests expect a reachable Neo4j at the default ``NEO4J_URI``.

Covers the overlap ranking used by community enrichment.
"""

import importlib.util
from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.community import COMMUNITY_LABEL, MEMBER_OF_RELATION
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.cypher.community_read import communities_for_entities_query
from agrag.cypher.entities import validate_identifier
from agrag.graphdb import build_graph_store


neo4j_missing = importlib.util.find_spec("neo4j") is None


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
@pytest.mark.xdist_group(name="community_label")
class TestCommunitiesForEntitiesOverlapIntegration:
    """``communities_for_entities_query`` ranks by overlap.

    Shares an ``xdist_group`` with ``TestDeleteCommunitiesBatchIntegration``:
    that test's ``delete_all_communities`` call deletes every ``Community``
    node in the database, so both classes must run on the same xdist
    worker to keep this test's own Community nodes from being wiped
    mid-run.
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

    async def test_overlap_ranking(self) -> None:
        """Creates C1([e1,e2]), C2([e2,e3]), C3([e3]) and checks ranking.

        Queries for [e2, e3]: C2 overlaps 2, C1 and C3 overlap 1.
        Asserts overlap is descending and C2 is the top result.
        """
        e1, e2, e3 = uuid4(), uuid4(), uuid4()
        c1, c2, c3 = uuid4(), uuid4(), uuid4()
        self.community_ids = [c1, c2, c3]
        try:
            await self.store.upsert_nodes(
                self.entity_label,
                [
                    NodeRecord(
                        id=e1, labels=[self.entity_label], properties={"name": "e1"}
                    ),
                    NodeRecord(
                        id=e2, labels=[self.entity_label], properties={"name": "e2"}
                    ),
                    NodeRecord(
                        id=e3, labels=[self.entity_label], properties={"name": "e3"}
                    ),
                ],
            )
            await self.store.upsert_nodes(
                COMMUNITY_LABEL,
                [
                    NodeRecord(
                        id=c1,
                        labels=[COMMUNITY_LABEL],
                        properties={
                            "title": "c1",
                            "summary": "s",
                            "rating": 1.0,
                            "rating_explanation": "r",
                            "findings": [],
                            "member_ids": [str(e1), str(e2)],
                            "internal_weight": 1.0,
                            "created_at": "2024-01-01T00:00:00",
                        },
                    ),
                    NodeRecord(
                        id=c2,
                        labels=[COMMUNITY_LABEL],
                        properties={
                            "title": "c2",
                            "summary": "s",
                            "rating": 1.0,
                            "rating_explanation": "r",
                            "findings": [],
                            "member_ids": [str(e2), str(e3)],
                            "internal_weight": 1.0,
                            "created_at": "2024-01-01T00:00:00",
                        },
                    ),
                    NodeRecord(
                        id=c3,
                        labels=[COMMUNITY_LABEL],
                        properties={
                            "title": "c3",
                            "summary": "s",
                            "rating": 1.0,
                            "rating_explanation": "r",
                            "findings": [],
                            "member_ids": [str(e3)],
                            "internal_weight": 1.0,
                            "created_at": "2024-01-01T00:00:00",
                        },
                    ),
                ],
            )
            await self.store.upsert_relations(
                [
                    RelationRecord(
                        id=uuid4(),
                        type=MEMBER_OF_RELATION,
                        start_id=e1,
                        end_id=c1,
                        properties={},
                    ),
                    RelationRecord(
                        id=uuid4(),
                        type=MEMBER_OF_RELATION,
                        start_id=e2,
                        end_id=c1,
                        properties={},
                    ),
                    RelationRecord(
                        id=uuid4(),
                        type=MEMBER_OF_RELATION,
                        start_id=e2,
                        end_id=c2,
                        properties={},
                    ),
                    RelationRecord(
                        id=uuid4(),
                        type=MEMBER_OF_RELATION,
                        start_id=e3,
                        end_id=c2,
                        properties={},
                    ),
                    RelationRecord(
                        id=uuid4(),
                        type=MEMBER_OF_RELATION,
                        start_id=e3,
                        end_id=c3,
                        properties={},
                    ),
                ]
            )

            rows = await self.store.execute_read(
                communities_for_entities_query(),
                {"entity_ids": [str(e2), str(e3)], "job_id": None, "top_k": 10},
            )

            assert len(rows) == 3
            overlaps = [r["overlap"] for r in rows]
            assert overlaps == sorted(overlaps, reverse=True)
            assert overlaps[0] == 2
            # execute_read runs the driver's Result.data(), which renders a
            # returned node as a plain dict of its properties (see
            # agrag.graphdb.neo4j.Neo4jGraphStore._run), so "id" is a
            # direct key.
            top_c = rows[0]["c"]
            top_id = top_c["id"]
            # Top community is C2 (the one with both e2 and e3).
            assert str(top_id) == str(c2)
            assert overlaps.count(1) == 2
        finally:
            await self.store.execute_write(
                "MATCH (n:Community) WHERE n.id IN $ids DETACH DELETE n",
                {"ids": [str(cid) for cid in self.community_ids]},
            )
