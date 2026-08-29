"""Unit tests for the Neo4j graph-store backend, with a fake driver.

The driver is injected as a fake, per ADR 0027, so no real Neo4j is required.
"""

from unittest import mock
from uuid import uuid4

import pytest

from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.vector_record import Distance
from agrag.graphdb.errors import GraphStoreMissingExtraError
from agrag.graphdb.neo4j import Neo4jGraphStore
from agrag.graphdb.settings import Neo4jSettings


class FakeSession:
    """A stand-in for a Neo4j async session backed by AsyncMocks."""

    def __init__(self) -> None:
        """Create the session with async mocks for reads and writes."""
        self.execute_read = mock.AsyncMock()
        self.execute_write = mock.AsyncMock()

    async def __aenter__(self) -> "FakeSession":
        """Enter the session context."""
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Exit the session context."""


class FakeDriver:
    """A stand-in for a Neo4j async driver."""

    def __init__(self) -> None:
        """Create the driver with async mocks for its lifecycle methods."""
        self.session = mock.MagicMock(return_value=FakeSession())
        self.verify_connectivity = mock.AsyncMock()
        self.close = mock.AsyncMock()

    @property
    def last_session(self) -> FakeSession:
        """Return the most recently created fake session."""
        return self.session.return_value


def _store() -> Neo4jGraphStore:
    """Build a Neo4jGraphStore wired to a FakeDriver."""
    return Neo4jGraphStore(settings=Neo4jSettings(), driver=FakeDriver())


class TestConnectClose:
    """connect and close manage the driver lifecycle."""

    async def test_connect_verifies(self) -> None:
        """Connect verifies connectivity on the driver."""
        store = _store()
        await store.connect()
        assert store._driver.verify_connectivity.await_count == 1

    async def test_close_closes_driver(self) -> None:
        """Close releases the driver."""
        store = _store()
        await store.connect()
        driver = store._driver
        await store.close()
        assert driver.close.await_count == 1
        assert store._driver is None


class TestExecute:
    """execute_read/execute_write delegate to managed session transactions."""

    async def test_execute_read_wraps_session(self) -> None:
        """execute_read delegates to a managed read transaction."""
        store = _store()
        store._driver.last_session.execute_read.return_value = [{"n": 1}]
        rows = await store.execute_read("MATCH (n) RETURN n")
        assert rows == [{"n": 1}]
        assert store._driver.last_session.execute_read.await_count == 1

    async def test_execute_write_wraps_session(self) -> None:
        """execute_write delegates to a managed write transaction."""
        store = _store()
        store._driver.last_session.execute_write.return_value = []
        await store.execute_write("MATCH (n) CREATE (m) RETURN m")
        assert store._driver.last_session.execute_write.await_count == 1


class TestUpsertNodes:
    """upsert_nodes validates the label, serializes, and writes in batches."""

    async def test_tracks_label_and_writes(self) -> None:
        """Upsert validates the label, serializes records, and writes."""
        store = _store()
        node = NodeRecord(id=uuid4(), labels=["Chunk"], properties={"text": "a"})
        await store.upsert_nodes("Chunk", [node])
        assert "Chunk" in store._known_labels
        call = store._driver.last_session.execute_write.call_args
        query, params = call.args[1], call.args[2]
        assert "MERGE (n:Chunk {id: record.id})" in query
        assert params == {
            "records": [{"id": str(node.id), "properties": {"text": "a"}}]
        }


class TestUpsertRelations:
    """upsert_relations groups records by type before writing."""

    async def test_groups_by_type(self) -> None:
        """Relations with different types issue distinct merge queries."""
        store = _store()
        rels = [
            RelationRecord(
                id=uuid4(),
                type="MENTIONS",
                start_id=uuid4(),
                end_id=uuid4(),
                properties={},
            ),
            RelationRecord(
                id=uuid4(),
                type="LINKS",
                start_id=uuid4(),
                end_id=uuid4(),
                properties={},
            ),
        ]
        await store.upsert_relations(rels)
        queries = [
            c.args[1] for c in store._driver.last_session.execute_write.call_args_list
        ]
        assert any("-[r:MENTIONS]->" in q for q in queries)
        assert any("-[r:LINKS]->" in q for q in queries)


class TestEnsureVectorIndex:
    """ensure_vector_index issues the native CREATE VECTOR INDEX query."""

    async def test_creates_index_and_tracks_label(self) -> None:
        """ensure_vector_index issues a CREATE VECTOR INDEX query."""
        store = _store()
        await store.ensure_vector_index(
            label="Chunk",
            vector_property="embedding",
            dimensions=4,
            distance=Distance.COSINE,
        )
        assert "Chunk" in store._known_labels
        query = store._driver.last_session.execute_write.call_args.args[1]
        assert "CREATE VECTOR INDEX Chunk_embedding_vector IF NOT EXISTS" in query


class TestSetupIdempotent:
    """setup_constraints/setup_indexes emit one DDL query per tracked label."""

    async def test_constraints_and_indexes_run_per_label(self) -> None:
        """setup_constraints/setup_indexes emit one DDL per tracked label."""
        store = _store()
        store._known_labels = {"Chunk", "Doc"}
        await store.setup_constraints()
        await store.setup_indexes()
        writes = store._driver.last_session.execute_write.call_args_list
        constraint_calls = [c for c in writes if "CONSTRAINT" in c.args[1]]
        index_calls = [
            c for c in writes if "INDEX" in c.args[1] and "VECTOR" not in c.args[1]
        ]
        assert len(constraint_calls) == 2
        assert len(index_calls) == 2


class TestVectorSearch:
    """vector_search maps native index result rows to VectorHit."""

    async def test_maps_node_to_vector_hit(self) -> None:
        """A result row becomes a VectorHit with the embedding stripped."""
        store = _store()
        rid = uuid4()
        store._driver.last_session.execute_read.return_value = [
            {
                "node": {
                    "id": str(rid),
                    "text": "sepsis",
                    "embedding": [0.1, 0.2, 0.3, 0.4],
                },
                "score": 0.91,
            }
        ]
        hits = await store.vector_search(
            label="Chunk",
            vector_property="embedding",
            query_vector=[0.1, 0.2, 0.3, 0.4],
            limit=5,
        )
        assert len(hits) == 1
        assert hits[0].id == rid
        assert hits[0].score == pytest.approx(0.91)
        assert hits[0].payload == {"text": "sepsis"}


class TestMissingExtra:
    """Without the extra installed, use raises, not ImportError."""

    async def test_connect_raises_missing_extra(self) -> None:
        """Connect without neo4j raises GraphStoreMissingExtraError."""
        store = Neo4jGraphStore()
        with (
            mock.patch.dict("sys.modules", {"neo4j": None}),
            pytest.raises(GraphStoreMissingExtraError) as exc_info,
        ):
            await store.connect()
        assert exc_info.value.extra == "neo4j"
