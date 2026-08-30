"""Integration tests for the Neo4j graph-store backend.

Run against the Docker Compose Neo4j instance from ``docker/docker-compose.ci.yml``
(``make dev-services-up``). The ``skipif`` only guards the missing extra; with
the extra installed the tests expect a reachable Neo4j at the default
``NEO4J_URI``.
"""

import asyncio
import importlib.util
import time
from uuid import uuid4

import pytest

from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import validate_identifier
from agrag.graphdb import build_graph_store
from agrag.graphdb.neo4j import Neo4jGraphStore
from agrag.graphdb.settings import Neo4jSettings
from tests.integration._vector_hit import assert_is_usable_vector_hit


neo4j_missing = importlib.util.find_spec("neo4j") is None

DIM = 4


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestNeo4jGraphStoreIntegration:
    """End-to-end behavior against a real Neo4j instance."""

    async def test_node_upsert_and_vector_search_round_trip(self) -> None:
        """Writes nodes, indexes them, and dense-searches them back."""
        store = build_graph_store("neo4j")
        await store.connect()
        # A unique label per run keeps this test isolated from other runs
        # sharing the same long-lived local Neo4j instance, matching the
        # unique-collection-name pattern tests/integration/vectordb/ uses.
        label = validate_identifier(f"Chunk_{uuid4().hex[:8]}")
        try:
            first_id = uuid4()
            await store.upsert_nodes(
                label,
                [
                    NodeRecord(
                        id=first_id,
                        labels=[label],
                        properties={
                            "text": "sepsis protocol",
                            "embedding": [1.0, 0, 0, 0],
                        },
                    ),
                    NodeRecord(
                        id=uuid4(),
                        labels=[label],
                        properties={"text": "flu guide", "embedding": [0, 1.0, 0, 0]},
                    ),
                ],
            )
            await store.setup_constraints()
            await store.ensure_vector_index(
                label=label,
                vector_property="embedding",
                dimensions=DIM,
                distance=Distance.COSINE,
            )
            hits = await self._search_with_retry(store, label, [1.0, 0, 0, 0])
            assert len(hits) >= 1
            assert_is_usable_vector_hit(
                hits[0], expected_id=first_id, expected_text="sepsis protocol"
            )
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.close()

    async def test_setup_constraints_is_idempotent(self) -> None:
        """Running setup_constraints twice does not error the second time."""
        store = build_graph_store("neo4j")
        await store.connect()
        label = validate_identifier(f"Doc_{uuid4().hex[:8]}")
        try:
            await store.upsert_nodes(
                label,
                [NodeRecord(id=uuid4(), labels=[label], properties={"text": "x"})],
            )
            await store.setup_constraints()
            await store.setup_constraints()
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.close()

    async def test_relation_upsert_links_nodes(self) -> None:
        """A relation MERGEs onto previously written nodes."""
        store = build_graph_store("neo4j")
        await store.connect()
        label = validate_identifier(f"Entity_{uuid4().hex[:8]}")
        try:
            start_id = uuid4()
            end_id = uuid4()
            await store.upsert_nodes(
                label,
                [
                    NodeRecord(id=start_id, labels=[label], properties={"name": "a"}),
                    NodeRecord(id=end_id, labels=[label], properties={"name": "b"}),
                ],
            )
            relation = RelationRecord(
                id=uuid4(),
                type="RELATES",
                start_id=start_id,
                end_id=end_id,
                properties={"weight": 1.0},
            )
            await store.upsert_relations([relation])
            rows = await store.execute_read(
                f"MATCH (:{label} {{id: $start_id}})-[r:RELATES]->"
                f"(:{label} {{id: $end_id}}) RETURN r.weight AS weight",
                {"start_id": str(start_id), "end_id": str(end_id)},
            )
            assert len(rows) == 1
            assert rows[0]["weight"] == 1.0
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.close()

    async def test_parallel_relations_keep_separate_identity(self) -> None:
        """Two same-type relations between the same nodes do not collapse."""
        store = build_graph_store("neo4j")
        await store.connect()
        label = validate_identifier(f"Entity_{uuid4().hex[:8]}")
        try:
            start_id = uuid4()
            end_id = uuid4()
            await store.upsert_nodes(
                label,
                [
                    NodeRecord(id=start_id, labels=[label], properties={"name": "a"}),
                    NodeRecord(id=end_id, labels=[label], properties={"name": "b"}),
                ],
            )
            relations = [
                RelationRecord(
                    id=uuid4(),
                    type="RELATES",
                    start_id=start_id,
                    end_id=end_id,
                    properties={"source": "doc1"},
                ),
                RelationRecord(
                    id=uuid4(),
                    type="RELATES",
                    start_id=start_id,
                    end_id=end_id,
                    properties={"source": "doc2"},
                ),
            ]
            await store.upsert_relations(relations)
            rows = await store.execute_read(
                f"MATCH (:{label} {{id: $start_id}})-[r:RELATES]->"
                f"(:{label} {{id: $end_id}}) RETURN r.id AS id, r.source AS source",
                {"start_id": str(start_id), "end_id": str(end_id)},
            )
            assert {row["id"] for row in rows} == {
                str(relations[0].id),
                str(relations[1].id),
            }
            assert {row["source"] for row in rows} == {"doc1", "doc2"}
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.close()

    async def test_repeated_write_of_one_id_updates_in_place(self) -> None:
        """Writing the same relation id twice updates it, not duplicates it."""
        store = build_graph_store("neo4j")
        await store.connect()
        label = validate_identifier(f"Entity_{uuid4().hex[:8]}")
        try:
            start_id = uuid4()
            end_id = uuid4()
            await store.upsert_nodes(
                label,
                [
                    NodeRecord(id=start_id, labels=[label], properties={"name": "a"}),
                    NodeRecord(id=end_id, labels=[label], properties={"name": "b"}),
                ],
            )
            rel_id = uuid4()
            await store.upsert_relations(
                [
                    RelationRecord(
                        id=rel_id,
                        type="RELATES",
                        start_id=start_id,
                        end_id=end_id,
                        properties={"weight": 1.0},
                    )
                ]
            )
            await store.upsert_relations(
                [
                    RelationRecord(
                        id=rel_id,
                        type="RELATES",
                        start_id=start_id,
                        end_id=end_id,
                        properties={"weight": 2.0},
                    )
                ]
            )
            rows = await store.execute_read(
                f"MATCH (:{label} {{id: $start_id}})-[r:RELATES]->"
                f"(:{label} {{id: $end_id}}) RETURN r.weight AS weight",
                {"start_id": str(start_id), "end_id": str(end_id)},
            )
            assert len(rows) == 1
            assert rows[0]["weight"] == 2.0
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.close()

    async def test_moving_endpoints_replaces_stale_relation(self) -> None:
        """Re-writing a relation id with a new end node drops the old edge."""
        store = build_graph_store("neo4j")
        await store.connect()
        label = validate_identifier(f"Entity_{uuid4().hex[:8]}")
        try:
            start_id = uuid4()
            first_end_id = uuid4()
            second_end_id = uuid4()
            await store.upsert_nodes(
                label,
                [
                    NodeRecord(id=start_id, labels=[label], properties={"name": "a"}),
                    NodeRecord(
                        id=first_end_id, labels=[label], properties={"name": "b"}
                    ),
                    NodeRecord(
                        id=second_end_id, labels=[label], properties={"name": "c"}
                    ),
                ],
            )
            rel_id = uuid4()
            await store.upsert_relations(
                [
                    RelationRecord(
                        id=rel_id,
                        type="RELATES",
                        start_id=start_id,
                        end_id=first_end_id,
                        properties={},
                    )
                ]
            )
            await store.upsert_relations(
                [
                    RelationRecord(
                        id=rel_id,
                        type="RELATES",
                        start_id=start_id,
                        end_id=second_end_id,
                        properties={},
                    )
                ]
            )
            rows = await store.execute_read(
                f"MATCH (:{label} {{id: $start_id}})-[r:RELATES {{id: $rel_id}}]->"
                f"(other:{label}) RETURN other.id AS end_id",
                {"start_id": str(start_id), "rel_id": str(rel_id)},
            )
            assert [row["end_id"] for row in rows] == [str(second_end_id)]
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.close()

    @staticmethod
    async def _search_with_retry(
        store: Neo4jGraphStore, label: str, vector: list[float]
    ) -> list:
        """Retry the vector search while the index warms up."""
        last: list = []
        for _ in range(10):
            last = await store.vector_search(
                label=label, vector_property="embedding", query_vector=vector, limit=2
            )
            if last:
                return last
            await asyncio.sleep(1)
        return last


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestConnectionFailure:
    """Behavior of ``connect()`` when the driver cannot authenticate."""

    async def test_wrong_password_raises_promptly(self) -> None:
        """A bad password fails fast with AuthError, not a pool-level timeout.

        Neo4j's driver rejects bad credentials during the handshake, well
        before any connection-pool or socket timeout would fire. Asserting a
        tight elapsed-time bound distinguishes that fast failure from a hang.
        """
        from neo4j.exceptions import AuthError  # noqa: PLC0415

        store = Neo4jGraphStore(
            settings=Neo4jSettings(
                uri="bolt://localhost:7687",
                username="neo4j",
                password="deliberately-wrong-password",
            )
        )
        start = time.monotonic()
        try:
            with pytest.raises(AuthError):
                await store.connect()
            elapsed = time.monotonic() - start
        finally:
            await store.close()
        assert elapsed < 10.0
