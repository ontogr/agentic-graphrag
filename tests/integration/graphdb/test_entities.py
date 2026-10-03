"""Integration tests for load_entities against a real Neo4j instance.

Run against the Docker Compose Neo4j instance from ``docker/docker-compose.ci.yml``
(``make dev-services-up``). The ``skipif`` only guards the missing extra; with
the extra installed the tests expect a reachable Neo4j at the default
``NEO4J_URI``.
"""

import importlib.util
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import tag_pending
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.graphdb.entities import load_entities


neo4j_missing = importlib.util.find_spec("neo4j") is None

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(loop_scope="module")
async def store() -> AsyncIterator[GraphStore]:
    """Yield a connected graph store."""
    graph_store = build_graph_store("neo4j")
    await graph_store.connect()
    try:
        yield graph_store
    finally:
        await graph_store.close()


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestLoadEntitiesIntegration:
    """Entities written to Neo4j come back through load_entities."""

    async def test_round_trips_stored_entities(self, store: GraphStore) -> None:
        """A written entity returns with its label, name, and properties."""
        tag = uuid4().hex[:8]
        entity = Entity(
            id=uuid4(),
            label="Show",
            name=f"Star Trek: Voyager {tag}",
            properties={"network": "UPN"},
        )
        try:
            await store.upsert_nodes("Show", [entity.to_node_record()])

            result = await load_entities(store, [entity.id, uuid4()])

            assert set(result) == {entity.id}
            assert result[entity.id].label == "Show"
            assert result[entity.id].name == entity.name
            assert result[entity.id].properties == {"network": "UPN"}
        finally:
            await store.execute_write(
                "MATCH (n {id: $id}) DETACH DELETE n", {"id": str(entity.id)}
            )

    async def test_excludes_nodes_an_in_flight_job_wrote(
        self, store: GraphStore
    ) -> None:
        """A node tagged with a pending job id is not returned."""
        committed = Entity(id=uuid4(), label="Person", name=f"Ada {uuid4().hex[:8]}")
        pending = Entity(id=uuid4(), label="Person", name=f"Bob {uuid4().hex[:8]}")
        try:
            await store.upsert_nodes(
                "Person",
                [
                    committed.to_node_record(),
                    tag_pending(pending.to_node_record(), uuid4()),
                ],
            )

            result = await load_entities(store, [committed.id, pending.id])

            assert set(result) == {committed.id}
        finally:
            await store.execute_write(
                "MATCH (n) WHERE n.id IN $ids DETACH DELETE n",
                {"ids": [str(committed.id), str(pending.id)]},
            )
