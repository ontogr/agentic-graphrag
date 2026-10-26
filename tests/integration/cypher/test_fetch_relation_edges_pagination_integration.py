"""Integration tests for fetch_relation_edges pagination against real Neo4j.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``). The
``skipif`` only guards the missing extra; with the extra installed the
tests expect a reachable Neo4j at the default ``NEO4J_URI``.
"""

import importlib.util
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest

from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.graph_schema import EntityType, GraphSchema, RelationType
from agrag.cypher.entities import validate_identifier
from agrag.ingestion.community import fetch_relation_edges
from tests.integration._backend import build_test_store


neo4j_missing = importlib.util.find_spec("neo4j") is None


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestFetchRelationEdgesPaginationIntegration:
    """``fetch_relation_edges`` paginates correctly."""

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Set up a fresh store with a unique entity label."""
        self.store = build_test_store()
        await self.store.connect()
        self.entity_label = validate_identifier(f"Entity_{uuid4().hex[:8]}")
        self.schema = GraphSchema(
            name="test",
            version="1",
            entities=[EntityType(label=self.entity_label, description="test entity")],
            relations=[
                RelationType(
                    label="KNOWS",
                    description="test relation",
                    patterns=[(self.entity_label, self.entity_label)],
                )
            ],
        )
        yield
        await self.store.execute_write(f"MATCH (n:{self.entity_label}) DETACH DELETE n")
        await self.store.close()

    async def test_pagination_with_page_size_two(self) -> None:
        """Return all 3 schema-matched relations across bounded pages."""
        node_ids = [uuid4() for _ in range(4)]
        try:
            await self.store.upsert_nodes(
                self.entity_label,
                [
                    NodeRecord(
                        id=nid, labels=[self.entity_label], properties={"name": f"n{i}"}
                    )
                    for i, nid in enumerate(node_ids)
                ],
            )
            await self.store.upsert_relations(
                [
                    RelationRecord(
                        id=uuid4(),
                        type="KNOWS",
                        start_id=node_ids[0],
                        end_id=node_ids[1],
                        properties={"source_chunk_ids": [str(uuid4())]},
                    ),
                    RelationRecord(
                        id=uuid4(),
                        type="KNOWS",
                        start_id=node_ids[1],
                        end_id=node_ids[2],
                        properties={"source_chunk_ids": []},
                    ),
                    RelationRecord(
                        id=uuid4(),
                        type="KNOWS",
                        start_id=node_ids[2],
                        end_id=node_ids[3],
                        properties={"source_chunk_ids": [str(uuid4()), str(uuid4())]},
                    ),
                ]
            )

            page_sizes: list[int] = []
            original_read = self.store.execute_read

            async def counting_read(query, parameters=None, **kw):  # type: ignore[no-untyped-def]
                rows = await original_read(query, parameters, **kw)
                page_sizes.append(len(rows))
                return rows

            self.store.execute_read = counting_read  # type: ignore[method-assign]
            try:
                edges = await fetch_relation_edges(
                    self.store, schema=self.schema, page_size=2
                )
            finally:
                self.store.execute_read = original_read  # type: ignore[method-assign]

            our_ids = {str(nid) for nid in node_ids}
            relevant = [e for e in edges if e[0] in our_ids and e[1] in our_ids]
            assert len(relevant) == 3
            assert page_sizes == [2, 1]
        finally:
            pass
