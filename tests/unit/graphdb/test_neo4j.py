"""Unit tests for the Neo4j graph-store backend, with a fake driver.

The driver is injected as a fake, so no real Neo4j is required.
"""

import asyncio
from typing import Any
from unittest import mock
from uuid import uuid4

import pytest

from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.cypher.schema import (
    node_id_constraint_query,
    relation_id_constraint_query,
    vector_index_name,
)
from agrag.graphdb.errors import (
    GraphStoreConstraintViolationError,
    GraphStoreMissingExtraError,
)
from agrag.graphdb.neo4j import _VECTOR_SEARCH_MAX_K, Neo4jGraphStore
from agrag.graphdb.settings import Neo4jSettings


class MockTransaction:
    """A stand-in for a Neo4j async explicit transaction."""

    def __init__(self) -> None:
        """Create the transaction with async mocks for run/commit/rollback."""
        result = mock.MagicMock()
        result.data = mock.AsyncMock(return_value=[])
        self.run = mock.AsyncMock(return_value=result)
        self.commit = mock.AsyncMock()
        self.rollback = mock.AsyncMock()


class MockSession:
    """A stand-in for a Neo4j async session backed by AsyncMocks."""

    def __init__(self) -> None:
        """Create the session with async mocks for reads, writes, and transactions."""
        self.execute_read = mock.AsyncMock()
        self.execute_write = mock.AsyncMock()
        self.begin_transaction = mock.AsyncMock(return_value=MockTransaction())

    async def __aenter__(self) -> "MockSession":
        """Enter the session context."""
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Exit the session context."""


class MockDriver:
    """A stand-in for a Neo4j async driver."""

    def __init__(self) -> None:
        """Create the driver with async mocks for its lifecycle methods."""
        self.session = mock.MagicMock(return_value=MockSession())
        self.verify_connectivity = mock.AsyncMock()
        self.close = mock.AsyncMock()

    @property
    def last_session(self) -> MockSession:
        """Return the most recently created fake session."""
        return self.session.return_value


def _store() -> Neo4jGraphStore:
    """Build a Neo4jGraphStore wired to a MockDriver."""
    store = Neo4jGraphStore(settings=Neo4jSettings(), driver=MockDriver())

    async def return_relation_ids(
        _run: object, query: str, parameters: dict[str, Any]
    ) -> list[dict[str, str]]:
        if "RETURN record.id AS id" not in query:
            return []
        return [{"id": record["id"]} for record in parameters["records"]]

    store._driver.last_session.execute_write.side_effect = return_relation_ids
    return store


def _node_constraint_name(label: str) -> str:
    """Derive the constraint name node_id_constraint_query issues for a label."""
    return node_id_constraint_query(label).split()[2]


def _relation_constraint_name(rel_type: str) -> str:
    """Derive the constraint name relation_id_constraint_query issues for a type."""
    return relation_id_constraint_query(rel_type).split()[2]


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

    async def test_concurrent_first_calls_build_driver_once(self) -> None:
        """Concurrent first calls build exactly one Neo4j driver, not one each."""
        build_calls = 0
        mock_driver = MockDriver()

        def mock_driver_ctor(*args, **kwargs):
            nonlocal build_calls
            build_calls += 1
            return mock_driver

        store = Neo4jGraphStore(settings=Neo4jSettings())
        with mock.patch(
            "neo4j.AsyncGraphDatabase.driver", side_effect=mock_driver_ctor
        ):
            first, second = await asyncio.gather(
                store._ensure_driver(), store._ensure_driver()
            )
        assert build_calls == 1
        assert first is second


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
            "records": [
                {
                    "id": str(node.id),
                    "properties": {"text": "a"},
                    "pending_job_id": None,
                }
            ]
        }

    async def test_isolates_record_specific_batch_failures(self) -> None:
        """A bad node does not block other nodes in its batch or later batches."""
        store = _store()
        store._identity_constraint_ready = True
        good, bad, later = (
            NodeRecord(id=uuid4(), labels=["Chunk"], properties={"name": value})
            for value in ("good", "bad", "later")
        )

        async def write(
            query: str, parameters: dict[str, object]
        ) -> list[dict[str, object]]:
            records = parameters["records"]
            assert isinstance(records, list)
            if len(records) == 2:
                raise GraphStoreConstraintViolationError("duplicate")
            if records[0]["id"] == str(bad.id):
                raise GraphStoreConstraintViolationError("duplicate")
            return []

        store.execute_write = mock.AsyncMock(side_effect=write)
        result = await store.upsert_nodes("Chunk", [good, bad, later], batch_size=2)

        assert result.written == 2
        assert [failure.id for failure in result.failures] == [str(bad.id)]
        assert store.execute_write.await_count == 4

    async def test_validation_failure_is_reported_per_record(self) -> None:
        """An unsafe content label only rejects its own node."""
        store = _store()
        store._identity_constraint_ready = True
        good = NodeRecord(id=uuid4(), labels=["Chunk"], properties={})
        bad = NodeRecord(id=uuid4(), labels=["not safe"], properties={})
        store.execute_write = mock.AsyncMock()

        result = await store.upsert_nodes("Chunk", [bad, good])

        assert result.written == 1
        assert result.failures[0].id == str(bad.id)
        store.execute_write.assert_awaited_once()

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
        writes = [
            c
            for c in store._driver.last_session.execute_write.call_args_list
            if "MERGE" in c.args[1]
        ]
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
            {"id": str(single.id), "properties": {"n": 1}, "pending_job_id": None}
        ]

    async def test_rejects_non_positive_batch_size(self) -> None:
        """A zero or negative batch_size raises instead of silently skipping."""
        store = _store()
        node = NodeRecord(id=uuid4(), labels=["Chunk"], properties={})
        with pytest.raises(ValueError):
            await store.upsert_nodes("Chunk", [node], batch_size=0)
        store._driver.last_session.execute_write.assert_not_called()

    async def test_creates_identity_constraint_before_first_write(self) -> None:
        """The identity uniqueness constraint is created before any node MERGE.

        Neo4j only makes MERGE atomic under concurrent writers once a
        uniqueness constraint backs the merged property, so the constraint
        must land before the first node write, not only via a separate
        setup_constraints call.
        """
        store = _store()
        node = NodeRecord(id=uuid4(), labels=["Chunk"], properties={})
        await store.upsert_nodes("Chunk", [node])
        writes = store._driver.last_session.execute_write.call_args_list
        assert _node_constraint_name(NODE_IDENTITY_LABEL) in writes[0].args[1]
        assert "MERGE" in writes[-1].args[1]

    async def test_concurrent_upserts_create_identity_constraint_once(self) -> None:
        """Concurrent first upserts issue the identity constraint exactly once.

        Regression guard: without serializing on a lock, two concurrent
        upsert_nodes calls could each observe the constraint as not yet
        created and both proceed to MERGE before it exists, letting Neo4j
        create two separate nodes for the same id.
        """
        store = _store()

        async def slow_write(
            _run: object, _query: str, _params: object
        ) -> list[dict[str, object]]:
            await asyncio.sleep(0)
            return []

        store._driver.last_session.execute_write.side_effect = slow_write
        first = NodeRecord(id=uuid4(), labels=["Chunk"], properties={})
        second = NodeRecord(id=uuid4(), labels=["Chunk"], properties={})
        await asyncio.gather(
            store.upsert_nodes("Chunk", [first]),
            store.upsert_nodes("Chunk", [second]),
        )
        writes = store._driver.last_session.execute_write.call_args_list
        constraint_calls = [
            c for c in writes if _node_constraint_name(NODE_IDENTITY_LABEL) in c.args[1]
        ]
        assert len(constraint_calls) == 1


class TestBatchWritePerItemIsolation:
    """Batch fallback isolates only errors tied to record data."""

    async def test_unknown_batch_error_aborts_without_retry(self) -> None:
        """An unknown error does not trigger individual retries."""
        store = _store()
        store.execute_write = mock.AsyncMock(side_effect=RuntimeError("outage"))
        records = [{"id": "1"}, {"id": "2"}]

        with pytest.raises(RuntimeError, match="outage"):
            await store._batch_write("QUERY", records, batch_size=2)

        store.execute_write.assert_awaited_once()

    async def test_syntax_error_aborts_without_retry(self) -> None:
        """A fixed query syntax error does not trigger individual retries."""
        neo4j = pytest.importorskip("neo4j.exceptions")
        store = _store()
        store.execute_write = mock.AsyncMock(
            side_effect=neo4j.CypherSyntaxError("invalid query")
        )

        with pytest.raises(neo4j.CypherSyntaxError):
            await store._batch_write("QUERY", [{"id": "1"}], batch_size=1)

        store.execute_write.assert_awaited_once()

    async def test_non_isolatable_error_during_retry_propagates(self) -> None:
        """A connection error during fallback is not captured as an item failure."""
        neo4j = pytest.importorskip("neo4j.exceptions")
        store = _store()
        store.execute_write = mock.AsyncMock(
            side_effect=[
                GraphStoreConstraintViolationError("duplicate"),
                neo4j.ServiceUnavailable("offline"),
            ]
        )

        with pytest.raises(neo4j.ServiceUnavailable):
            await store._batch_write("QUERY", [{"id": "1"}], batch_size=1)

        assert store.execute_write.await_count == 2

    async def test_all_individual_records_can_fail(self) -> None:
        """Fallback visits every record even when each individual write fails."""
        store = _store()
        store.execute_write = mock.AsyncMock(
            side_effect=GraphStoreConstraintViolationError("duplicate")
        )
        result = await store._batch_write(
            "QUERY", [{"id": "1"}, {"id": "2"}], batch_size=2
        )

        assert result.written == 0
        assert [failure.id for failure in result.failures] == ["1", "2"]
        assert store.execute_write.await_count == 3

    async def test_empty_records_do_not_write(self) -> None:
        """An empty input returns an empty result without touching the driver."""
        store = _store()
        store.execute_write = mock.AsyncMock()

        result = await store._batch_write("QUERY", [], batch_size=2)

        assert result.written == 0
        assert result.failures == []
        store.execute_write.assert_not_awaited()


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

    async def test_validation_failure_is_reported_per_relation(self) -> None:
        """An unsafe relationship type only rejects its own relation."""
        store = _store()
        first = RelationRecord(
            id=uuid4(),
            type="not safe",
            start_id=uuid4(),
            end_id=uuid4(),
            properties={},
        )
        second = RelationRecord(
            id=uuid4(),
            type="MENTIONS",
            start_id=uuid4(),
            end_id=uuid4(),
            properties={},
        )

        result = await store.upsert_relations([first, second])

        assert result.written == 1
        assert [failure.id for failure in result.failures] == [str(first.id)]

    async def test_missing_endpoints_are_reported_as_failures(self) -> None:
        """A relation with no matched endpoints is not counted as written."""
        store = _store()

        async def no_rows(
            _run: object, _query: str, _parameters: dict[str, Any]
        ) -> list[Any]:
            return []

        store._driver.last_session.execute_write.side_effect = no_rows
        relation = RelationRecord(
            id=uuid4(),
            type="MENTIONS",
            start_id=uuid4(),
            end_id=uuid4(),
            properties={},
        )

        result = await store.upsert_relations([relation])

        assert result.written == 0
        assert [failure.id for failure in result.failures] == [str(relation.id)]
        assert [failure.error_type for failure in result.failures] == [
            "MissingEndpoint"
        ]

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

    async def test_creates_relation_constraint_before_first_write(self) -> None:
        """A relation type's identity constraint is created before its first MERGE.

        Neo4j only makes MERGE atomic under concurrent writers once a
        uniqueness constraint backs the merged property, so the constraint
        must land before the first relationship write for that type, not
        only via a separate setup_constraints call.
        """
        store = _store()
        rel = RelationRecord(
            id=uuid4(),
            type="MENTIONS",
            start_id=uuid4(),
            end_id=uuid4(),
            properties={},
        )
        await store.upsert_relations([rel])
        writes = store._driver.last_session.execute_write.call_args_list
        assert _relation_constraint_name("MENTIONS") in writes[0].args[1]
        assert "-[r:MENTIONS {id: record.id}]->" in writes[-1].args[1]

    async def test_concurrent_upserts_create_relation_constraint_once(self) -> None:
        """Concurrent first upserts of one type issue its constraint exactly once.

        Regression guard: without serializing on a lock, two concurrent
        upsert_relations calls for the same type could each observe the
        constraint as not yet created and both proceed to MERGE before it
        exists, letting Neo4j create two separate relationships for the
        same id.
        """
        store = _store()

        async def slow_write(
            _run: object, _query: str, _params: object
        ) -> list[dict[str, object]]:
            await asyncio.sleep(0)
            return []

        store._driver.last_session.execute_write.side_effect = slow_write
        first = RelationRecord(
            id=uuid4(),
            type="MENTIONS",
            start_id=uuid4(),
            end_id=uuid4(),
            properties={},
        )
        second = RelationRecord(
            id=uuid4(),
            type="MENTIONS",
            start_id=uuid4(),
            end_id=uuid4(),
            properties={},
        )
        await asyncio.gather(
            store.upsert_relations([first]),
            store.upsert_relations([second]),
        )
        writes = store._driver.last_session.execute_write.call_args_list
        constraint_calls = [
            c for c in writes if _relation_constraint_name("MENTIONS") in c.args[1]
        ]
        assert len(constraint_calls) == 1


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
        name = vector_index_name("Chunk", "embedding")
        assert f"CREATE VECTOR INDEX {name} IF NOT EXISTS" in query


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
        # Chunk + Doc, each with an id and a merge_key uniqueness constraint,
        # plus the identity-anchor, merge-key-alias, and CutoverJob
        # document_key constraints every store sets up once.
        assert len(constraint_calls) == 7
        assert any(NODE_IDENTITY_LABEL in c.args[1] for c in constraint_calls)
        assert any("merge_key_unique" in c.args[1] for c in constraint_calls)
        assert any("agragmergealias" in c.args[1].lower() for c in constraint_calls)
        assert any("cutoverjob_document_key" in c.args[1] for c in constraint_calls)
        # One merge-key index per label plus the CutoverJob status index.
        assert len(index_calls) == 3
        assert any("_merge_key_index" in c.args[1] for c in index_calls)
        assert any("cutover_job_status_index" in c.args[1] for c in index_calls)

    async def test_constraints_run_per_relation_type(self) -> None:
        """setup_constraints also emits one DDL per tracked relation type."""
        store = _store()
        store._known_relation_types = {"MENTIONS", "LINKS"}
        await store.setup_constraints()
        writes = store._driver.last_session.execute_write.call_args_list
        constraint_calls = [c.args[1] for c in writes if "FOR ()-[r:" in c.args[1]]
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
        assert any(_node_constraint_name("Existing") in c.args[1] for c in writes)

    async def test_unsafe_live_label_does_not_block_other_constraints(self) -> None:
        """One database label outside our identifier subset does not halt setup.

        Regression guard: Neo4j allows labels with spaces or hyphens that our
        Cypher builders cannot safely interpolate unquoted. Raising on one
        such name discovered live would abort the whole constraint loop
        before it reached any later, valid label.
        """
        store = _store()

        def fake_execute_read(_run: object, query: str, _params: object) -> list:
            if "db.labels" in query:
                return [{"label": "Weird Label"}, {"label": "Valid"}]
            return []

        store._driver.last_session.execute_read.side_effect = fake_execute_read
        await store.setup_constraints()
        writes = store._driver.last_session.execute_write.call_args_list
        assert any(_node_constraint_name("Valid") in c.args[1] for c in writes)
        assert not any("Weird Label" in c.args[1] for c in writes)

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
        assert any(
            _relation_constraint_name("EXISTING_REL") in c.args[1] for c in writes
        )

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
            c for c in writes if _node_constraint_name(NODE_IDENTITY_LABEL) in c.args[1]
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

    async def test_unfiltered_search_overfetches_to_exclude_pending_records(
        self,
    ) -> None:
        """The pending-record filter overfetches until it can return visible hits."""
        store = _store()
        store._driver.last_session.execute_read.return_value = []
        await store.vector_search(
            label="Chunk",
            vector_property="embedding",
            query_vector=[0.1, 0.2, 0.3, 0.4],
            limit=5,
        )
        assert store._driver.last_session.execute_read.await_count == 5

    @pytest.mark.parametrize("limit", [0, -1])
    async def test_rejects_non_positive_limit(self, limit: int) -> None:
        """A non-positive limit raises instead of reaching Neo4j.

        Regression guard: with filters set, a non-positive k starts the
        escalation loop stuck comparing an always-satisfied
        len(rows) >= limit against a k the overfetch multiplier can never
        grow past zero, so it would keep querying Neo4j with that same
        unusable k instead of escalating toward real candidates.
        """
        store = _store()
        with pytest.raises(ValueError, match="positive"):
            await store.vector_search(
                label="Chunk",
                vector_property="embedding",
                query_vector=[0.1, 0.2, 0.3, 0.4],
                limit=limit,
                filters={"kind": "doc"},
            )
        store._driver.last_session.execute_read.assert_not_called()

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

    async def test_missing_index_returns_empty(self) -> None:
        """A label with no vector index returns no hits instead of raising.

        A filter naming a label that was never ingested has no index to
        search; that is an empty result set, not a retrieval failure.
        """
        store = _store()
        store._driver.last_session.execute_read.side_effect = RuntimeError(
            "Failed to invoke procedure `db.index.vector.queryNodes`: "
            "Caused by: java.lang.IllegalArgumentException: "
            "There is no such vector schema index: "
            "idx_6_Bogus_9_embedding_vector"
        )
        hits = await store.vector_search(
            label="Bogus",
            vector_property="embedding",
            query_vector=[0.1, 0.2, 0.3, 0.4],
            limit=5,
        )
        assert hits == []

    async def test_unrelated_driver_error_still_raises(self) -> None:
        """A driver error other than a missing index keeps propagating."""
        store = _store()
        store._driver.last_session.execute_read.side_effect = RuntimeError(
            "connection lost"
        )
        with pytest.raises(RuntimeError, match="connection lost"):
            await store.vector_search(
                label="Chunk",
                vector_property="embedding",
                query_vector=[0.1, 0.2, 0.3, 0.4],
                limit=5,
            )


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


class TestTransaction:
    """transaction() opens one explicit transaction and commits or rolls it back."""

    async def test_commits_on_clean_exit(self) -> None:
        """A clean exit from the block commits, and never rolls back."""
        store = _store()
        async with store.transaction() as txn:
            await txn.execute_write("MATCH (n) RETURN n")
        tx = store._driver.last_session.begin_transaction.return_value
        assert tx.commit.await_count == 1
        assert tx.rollback.await_count == 0

    async def test_rolls_back_and_reraises_on_exception(self) -> None:
        """An exception in the block rolls back and propagates, no commit."""
        store = _store()
        with pytest.raises(ValueError, match="boom"):
            async with store.transaction() as txn:
                await txn.execute_write("MATCH (n) RETURN n")
                raise ValueError("boom")
        tx = store._driver.last_session.begin_transaction.return_value
        assert tx.rollback.await_count == 1
        assert tx.commit.await_count == 0

    async def test_execute_write_runs_against_the_open_transaction(self) -> None:
        """execute_write inside the block runs on the transaction, not a new one."""
        store = _store()
        tx = store._driver.last_session.begin_transaction.return_value
        tx.run.return_value.data = mock.AsyncMock(return_value=[{"n": 1}])
        async with store.transaction() as txn:
            rows = await txn.execute_write("MATCH (n) RETURN n", {"a": 1})
        assert rows == [{"n": 1}]
        tx.run.assert_awaited_once_with("MATCH (n) RETURN n", {"a": 1})

    async def test_upsert_nodes_runs_against_the_open_transaction(self) -> None:
        """Upsert inside the block runs through the transaction and tracks labels."""
        store = _store()
        tx = store._driver.last_session.begin_transaction.return_value
        node = NodeRecord(id=uuid4(), labels=["Person"], properties={"name": "Ada"})
        async with store.transaction() as txn:
            await txn.upsert_nodes("Person", [node])
        assert "Person" in store._known_labels
        query, params = tx.run.call_args.args
        assert f"MERGE (n:{NODE_IDENTITY_LABEL} {{id: record.id}})" in query
        assert params == {
            "records": [
                {
                    "id": str(node.id),
                    "properties": {"name": "Ada"},
                    "pending_job_id": None,
                }
            ]
        }

    async def test_ensures_identity_constraint_before_opening(self) -> None:
        """The identity constraint is created once, before the transaction opens."""
        store = _store()
        async with store.transaction():
            pass
        writes = store._driver.last_session.execute_write.call_args_list
        assert any(NODE_IDENTITY_LABEL in c.args[1] for c in writes)

    async def test_ensures_merge_alias_constraint_before_opening(self) -> None:
        """The merge-key alias constraint is created before the transaction opens.

        apply_merge writes an alias row (upsert_merge_alias_query) inside
        this transaction; without the constraint in place first, MERGE on
        merge_key would not be atomic under concurrent writers.
        """
        store = _store()
        async with store.transaction():
            pass
        writes = store._driver.last_session.execute_write.call_args_list
        assert any("agragmergealias" in c.args[1].lower() for c in writes)

    async def test_upsert_relations_creates_relation_constraint_before_first_write(
        self,
    ) -> None:
        """A relation type's constraint is created before its first write in a tx.

        Regression guard: ``_Neo4jTransaction.upsert_relations`` used to only
        call ``register_relation_types``, which is documented bookkeeping
        that issues no write, so a relationship type written only inside a
        transaction never got its per-type identity constraint. Without it,
        concurrent explicit transactions could create duplicate
        relationships for the same id.
        """
        store = _store()
        tx = store._driver.last_session.begin_transaction.return_value
        events: list[tuple[str, str]] = []

        async def record_session_write(
            _run: object, query: str, _params: object
        ) -> list[dict[str, object]]:
            events.append(("constraint", query))
            return []

        store._driver.last_session.execute_write.side_effect = record_session_write

        tx_result = tx.run.return_value

        async def record_tx_run(query: str, _params: object) -> object:
            events.append(("write", query))
            return tx_result

        tx.run.side_effect = record_tx_run

        rel = RelationRecord(
            id=uuid4(),
            type="MENTIONS",
            start_id=uuid4(),
            end_id=uuid4(),
            properties={},
        )
        async with store.transaction() as txn:
            await txn.upsert_relations([rel])

        constraint_name = _relation_constraint_name("MENTIONS")
        constraint_indexes = [
            i
            for i, (kind, query) in enumerate(events)
            if kind == "constraint" and constraint_name in query
        ]
        write_indexes = [
            i
            for i, (kind, query) in enumerate(events)
            if kind == "write" and "-[r:MENTIONS {id: record.id}]->" in query
        ]
        assert constraint_indexes, f"no MENTIONS constraint write in {events}"
        assert write_indexes, f"no MENTIONS relationship write in {events}"
        assert constraint_indexes[0] < write_indexes[0]


class TestExecuteReadTimeout:
    """execute_read applies the server-side transaction timeout."""

    async def test_wraps_transaction_function_with_timeout(self) -> None:
        """A requested timeout rides on the transaction function."""
        pytest.importorskip("neo4j")
        store = _store()
        await store.execute_read("MATCH (n) RETURN n", timeout=7.5)
        session = store._driver.last_session
        tx_function = session.execute_read.call_args.args[0]
        assert tx_function.timeout == 7.5

    async def test_no_timeout_by_default(self) -> None:
        """Without a timeout, the transaction function carries none."""
        store = _store()
        await store.execute_read("MATCH (n) RETURN n")
        session = store._driver.last_session
        tx_function = session.execute_read.call_args.args[0]
        assert getattr(tx_function, "timeout", None) is None

    async def test_timeout_reads_rows_normally(self) -> None:
        """A timed read still returns the transaction function's rows."""
        pytest.importorskip("neo4j")
        store = _store()
        session = store._driver.last_session
        session.execute_read = mock.AsyncMock(return_value=[{"n": 1}])
        rows = await store.execute_read("MATCH (n) RETURN n", timeout=7.5)
        assert rows == [{"n": 1}]
