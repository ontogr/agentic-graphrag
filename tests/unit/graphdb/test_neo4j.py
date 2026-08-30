"""Unit tests for the Neo4j graph-store backend, with a fake driver.

The driver is injected as a fake, per ADR 0027, so no real Neo4j is required.
"""

from unittest import mock
from uuid import uuid4

import pytest

from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.graphdb.errors import GraphStoreMissingExtraError
from agrag.graphdb.neo4j import _VECTOR_SEARCH_MAX_K, Neo4jGraphStore
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
        assert f"MERGE (n:{NODE_IDENTITY_LABEL} {{id: record.id}})" in query
        assert "SET n:Chunk" in query
        assert params == {
            "records": [{"id": str(node.id), "properties": {"text": "a"}}]
        }

    async def test_tracks_every_label_on_multi_label_node(self) -> None:
        """A multi-label node tracks each of its labels, not only the call label."""
        store = _store()
        node = NodeRecord(
            id=uuid4(), labels=["Chunk", "Entity"], properties={"text": "a"}
        )
        await store.upsert_nodes("Chunk", [node])
        assert store._known_labels == {"Chunk", "Entity"}
        query = store._driver.last_session.execute_write.call_args.args[1]
        assert f"MERGE (n:{NODE_IDENTITY_LABEL} {{id: record.id}})" in query
        assert "SET n:Chunk:Entity" in query

    async def test_merge_identity_is_independent_of_content_labels(self) -> None:
        """MERGE never targets the mutable content labels directly.

        Regression guard: MERGE-ing on the full requested label set would
        only match a node that already has every one of those labels, so
        adding a label to an existing same-id node would create a duplicate
        instead of updating it.
        """
        store = _store()
        node = NodeRecord(id=uuid4(), labels=["Chunk", "Entity"], properties={})
        await store.upsert_nodes("Chunk", [node])
        query = store._driver.last_session.execute_write.call_args.args[1]
        assert "MERGE (n:Chunk" not in query
        assert "MERGE (n:Entity" not in query

    async def test_groups_mixed_label_batch_into_separate_writes(self) -> None:
        """Records with different label sets get separate MERGE queries."""
        store = _store()
        single = NodeRecord(id=uuid4(), labels=["Chunk"], properties={"n": 1})
        compound = NodeRecord(
            id=uuid4(), labels=["Chunk", "Entity"], properties={"n": 2}
        )
        await store.upsert_nodes("Chunk", [single, compound])
        writes = store._driver.last_session.execute_write.call_args_list
        assert len(writes) == 2
        queries = {call.args[1] for call in writes}
        assert any("SET n:Chunk " in q and "SET n:Chunk:" not in q for q in queries)
        assert any("SET n:Chunk:Entity" in q for q in queries)
        single_call = next(
            c
            for c in writes
            if "SET n:Chunk " in c.args[1] and "SET n:Chunk:" not in c.args[1]
        )
        assert single_call.args[2]["records"] == [
            {"id": str(single.id), "properties": {"n": 1}}
        ]

    async def test_rejects_non_positive_batch_size(self) -> None:
        """A zero or negative batch_size raises instead of silently skipping."""
        store = _store()
        node = NodeRecord(id=uuid4(), labels=["Chunk"], properties={})
        with pytest.raises(ValueError):
            await store.upsert_nodes("Chunk", [node], batch_size=0)
        store._driver.last_session.execute_write.assert_not_called()


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
        assert any("-[r:MENTIONS {id: record.id}]->" in q for q in queries)
        assert any("-[r:LINKS {id: record.id}]->" in q for q in queries)
        assert store._known_relation_types == {"MENTIONS", "LINKS"}

    async def test_rejects_non_positive_batch_size(self) -> None:
        """A zero or negative batch_size raises instead of silently skipping."""
        store = _store()
        rel = RelationRecord(
            id=uuid4(),
            type="MENTIONS",
            start_id=uuid4(),
            end_id=uuid4(),
            properties={},
        )
        with pytest.raises(ValueError):
            await store.upsert_relations([rel], batch_size=-1)
        store._driver.last_session.execute_write.assert_not_called()


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
        # Chunk + Doc, plus the identity-anchor constraint every store sets up.
        assert len(constraint_calls) == 3
        assert any(NODE_IDENTITY_LABEL in c.args[1] for c in constraint_calls)
        assert len(index_calls) == 2

    async def test_constraints_run_per_relation_type(self) -> None:
        """setup_constraints also emits one DDL per tracked relation type."""
        store = _store()
        store._known_relation_types = {"MENTIONS", "LINKS"}
        await store.setup_constraints()
        writes = store._driver.last_session.execute_write.call_args_list
        constraint_calls = [c.args[1] for c in writes if "rel_id_unique" in c.args[1]]
        assert len(constraint_calls) == 2

    async def test_discovers_labels_already_in_database(self) -> None:
        """A label never written by this instance still gets set up.

        A fresh store instance has an empty ``_known_labels``, so a label
        already in the database must come from a live query instead, letting
        a fresh store set up an existing database without rewriting records.
        """
        store = _store()

        def fake_execute_read(_run: object, query: str, _params: object) -> list:
            if "db.labels" in query:
                return [{"label": "Existing"}]
            return []

        store._driver.last_session.execute_read.side_effect = fake_execute_read
        await store.setup_constraints()
        writes = store._driver.last_session.execute_write.call_args_list
        assert any("Existing_id_unique" in c.args[1] for c in writes)

    async def test_discovers_relation_types_already_in_database(self) -> None:
        """A relation type never written by this instance still gets set up."""
        store = _store()

        def fake_execute_read(_run: object, query: str, _params: object) -> list:
            if "db.relationshipTypes" in query:
                return [{"relationshipType": "EXISTING_REL"}]
            return []

        store._driver.last_session.execute_read.side_effect = fake_execute_read
        await store.setup_constraints()
        writes = store._driver.last_session.execute_write.call_args_list
        assert any("EXISTING_REL_rel_id_unique" in c.args[1] for c in writes)

    async def test_discovered_identity_label_is_not_double_constrained(self) -> None:
        """The identity anchor discovered live does not get a duplicate constraint."""
        store = _store()

        def fake_execute_read(_run: object, query: str, _params: object) -> list:
            if "db.labels" in query:
                return [{"label": NODE_IDENTITY_LABEL}]
            return []

        store._driver.last_session.execute_read.side_effect = fake_execute_read
        await store.setup_constraints()
        writes = store._driver.last_session.execute_write.call_args_list
        identity_calls = [
            c for c in writes if f"{NODE_IDENTITY_LABEL}_id_unique" in c.args[1]
        ]
        assert len(identity_calls) == 1


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

    async def test_unfiltered_search_issues_one_call(self) -> None:
        """Without filters, a single call is made even if results are sparse."""
        store = _store()
        store._driver.last_session.execute_read.return_value = []
        await store.vector_search(
            label="Chunk",
            vector_property="embedding",
            query_vector=[0.1, 0.2, 0.3, 0.4],
            limit=5,
        )
        assert store._driver.last_session.execute_read.await_count == 1

    async def test_overfetches_past_a_filtered_out_top_match(self) -> None:
        """A closer node that fails the filter does not hide a farther match.

        With ``limit=1`` the vector procedure's first pass (``k=1``) only
        considers the single nearest node, which the filter excludes. Only
        escalating ``k`` past the multiplier's second step surfaces the
        farther, filter-matching node.
        """
        store = _store()
        rid = uuid4()

        def fake_execute_read(_run, _query, parameters):
            if parameters["k"] < 16:
                return []
            return [
                {
                    "node": {"id": str(rid), "text": "note", "kind": "doc"},
                    "score": 0.5,
                }
            ]

        store._driver.last_session.execute_read.side_effect = fake_execute_read
        hits = await store.vector_search(
            label="Chunk",
            vector_property="embedding",
            query_vector=[0.1, 0.2, 0.3, 0.4],
            limit=1,
            filters={"kind": "doc"},
        )
        assert len(hits) == 1
        assert hits[0].id == rid
        assert store._driver.last_session.execute_read.await_count == 3

    async def test_overfetch_gives_up_at_the_k_ceiling(self) -> None:
        """A filter matching nothing stops escalating at the k ceiling."""
        store = _store()
        store._driver.last_session.execute_read.return_value = []
        hits = await store.vector_search(
            label="Chunk",
            vector_property="embedding",
            query_vector=[0.1, 0.2, 0.3, 0.4],
            limit=1,
            filters={"kind": "doc"},
        )
        assert hits == []
        last_params = store._driver.last_session.execute_read.call_args.args[2]
        assert last_params["k"] == _VECTOR_SEARCH_MAX_K


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
