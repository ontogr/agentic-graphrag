"""Unit tests for the Neo4j graph-store backend, with a fake driver.

The driver is injected as a fake, so no real Neo4j is required.
"""

import asyncio
from typing import Any
from unittest import mock
from uuid import uuid4

import pytest

from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.cypher.schema import (
    node_id_constraint_query,
    relation_id_constraint_query,
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


class TestUpsertNodes:
    """upsert_nodes validates the label, serializes, and writes in batches."""

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

    async def test_rejects_non_positive_batch_size(self) -> None:
        """A zero or negative batch_size raises instead of silently skipping."""
        store = _store()
        node = NodeRecord(id=uuid4(), labels=["Chunk"], properties={})
        with pytest.raises(ValueError):
            await store.upsert_nodes("Chunk", [node], batch_size=0)
        store._driver.last_session.execute_write.assert_not_called()

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


class TestVectorSearch:
    """vector_search maps native index result rows to VectorHit."""

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
