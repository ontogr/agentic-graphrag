"""Unit tests for the Neo4j graph-store backend, with a fake driver.

The driver is injected as a fake, so no real Neo4j is required.
"""

import asyncio
from typing import Any
from unittest import mock
from uuid import uuid4

import pytest
from neo4j import NotificationDisabledClassification
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind, StatusCode

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


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Return a provider wired to an in-memory exporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


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

    async def test_driver_disables_only_unrecognized_notifications(self) -> None:
        """The driver drops UNRECOGNIZED notifications and keeps every other one."""
        store = Neo4jGraphStore(settings=Neo4jSettings())
        with mock.patch(
            "neo4j.AsyncGraphDatabase.driver", return_value=MockDriver()
        ) as build:
            await store._ensure_driver()
        kwargs = build.call_args.kwargs
        assert kwargs["notifications_disabled_classifications"] == [
            NotificationDisabledClassification.UNRECOGNIZED
        ]
        assert "notifications_min_severity" not in kwargs


class TestUpsertNodes:
    """upsert_nodes validates the label, serializes, and writes in batches."""

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


class TestPendingJobTag:
    """A job id passed to an upsert tags the records the store writes."""

    async def test_transaction_upserts_tag_records_with_the_job_id(self) -> None:
        """Node and relation writes inside a transaction carry the job id."""
        store = _store()
        store._identity_constraint_ready = True
        job_id = uuid4()
        node = NodeRecord(id=uuid4(), labels=["Chunk"], properties={})
        relation = RelationRecord(
            id=uuid4(), type="MENTIONS", start_id=uuid4(), end_id=uuid4(), properties={}
        )

        async with store.transaction() as txn:
            await txn.upsert_nodes("Chunk", [node], pending_job_id=job_id)
            await txn.upsert_relations([relation], pending_job_id=job_id)

        tx = store._driver.last_session.begin_transaction.return_value
        sent = [
            call.args[1]["records"][0]
            for call in tx.run.await_args_list
            if "records" in call.args[1]
        ]
        assert [r["pending_job_id"] for r in sent] == [str(job_id)] * 2


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


class TestExecuteSpans:
    """Traced execute_read/write export CLIENT spans with query attributes."""

    async def test_execute_read_span_kind_and_attributes(self) -> None:
        """execute_read exports a CLIENT span with system/namespace/text."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("test")
        driver = MockDriver()
        driver.last_session.execute_read.return_value = []
        store = Neo4jGraphStore(settings=Neo4jSettings(), driver=driver, tracer=tracer)
        await store.execute_read("MATCH (n) RETURN n", {"name": "alice"})
        (span,) = exporter.get_finished_spans()
        assert span.name == "agrag.graphdb.execute_read"
        assert span.kind is SpanKind.CLIENT
        assert (span.attributes or {})["db.system.name"] == "neo4j"
        assert (span.attributes or {})["db.namespace"] == "neo4j"
        assert (span.attributes or {})["db.query.text"] == "MATCH (n) RETURN n"
        assert (span.attributes or {})["db.query.parameter.name"] == "alice"
        assert span.status.status_code is StatusCode.UNSET

    async def test_execute_write_error_marks_span_error(self) -> None:
        """A failing execute_write marks its span ERROR with one event."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("test")
        driver = MockDriver()
        driver.last_session.execute_write.side_effect = RuntimeError("down")
        store = Neo4jGraphStore(settings=Neo4jSettings(), driver=driver, tracer=tracer)
        with pytest.raises(RuntimeError, match="down"):
            await store.execute_write("MERGE (n) RETURN n")
        (span,) = exporter.get_finished_spans()
        assert span.name == "agrag.graphdb.execute_write"
        assert span.kind is SpanKind.CLIENT
        assert span.status.status_code is StatusCode.ERROR
        assert len(list(span.events)) == 1


class TestUpsertTracing:
    """Traced upsert_nodes exports INTERNAL span with written counts."""

    async def test_upsert_nodes_span_kind_and_written(self) -> None:
        """upsert_nodes exports INTERNAL with written/failures attributes."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("test")
        store = _store()
        store._tracer = tracer
        node = NodeRecord(id=uuid4(), labels=["Doc"], properties={"text": "a"})
        outcome = await store.upsert_nodes("Doc", [node])
        assert outcome.written == 1
        spans = exporter.get_finished_spans()
        (outer,) = [s for s in spans if s.name == "agrag.graphdb.upsert_nodes"]
        assert outer.kind is SpanKind.INTERNAL
        assert (outer.attributes or {})["agrag.written"] == 1
        assert (outer.attributes or {})["agrag.failures_count"] == 0
        assert outer.status.status_code is StatusCode.UNSET
        assert [s for s in spans if s.name == "agrag.graphdb.execute_write"]

    async def test_batch_size_reports_submitted_batch_not_configured_limit(
        self,
    ) -> None:
        """A short write reports the batch it sent, not the configured limit."""
        provider, exporter = _provider()
        store = _store()
        store._tracer = provider.get_tracer("test")
        nodes = [
            NodeRecord(id=uuid4(), labels=["Doc"], properties={"text": str(index)})
            for index in range(3)
        ]
        await store.upsert_nodes("Doc", nodes, batch_size=256)
        (outer,) = [
            s
            for s in exporter.get_finished_spans()
            if s.name == "agrag.graphdb.upsert_nodes"
        ]
        assert (outer.attributes or {})["db.operation.batch.size"] == 3

    async def test_batch_size_reports_full_batch_when_it_fills_the_limit(self) -> None:
        """A write larger than the limit reports the limit it actually sent."""
        provider, exporter = _provider()
        store = _store()
        store._tracer = provider.get_tracer("test")
        nodes = [
            NodeRecord(id=uuid4(), labels=["Doc"], properties={"text": str(index)})
            for index in range(5)
        ]
        await store.upsert_nodes("Doc", nodes, batch_size=2)
        (outer,) = [
            s
            for s in exporter.get_finished_spans()
            if s.name == "agrag.graphdb.upsert_nodes"
        ]
        assert (outer.attributes or {})["db.operation.batch.size"] == 2

    async def test_batch_size_omitted_for_a_single_record_write(self) -> None:
        """One record is a single operation, not a batch, so it is not reported."""
        provider, exporter = _provider()
        store = _store()
        store._tracer = provider.get_tracer("test")
        node = NodeRecord(id=uuid4(), labels=["Doc"], properties={"text": "a"})
        await store.upsert_nodes("Doc", [node])
        (outer,) = [
            s
            for s in exporter.get_finished_spans()
            if s.name == "agrag.graphdb.upsert_nodes"
        ]
        assert "db.operation.batch.size" not in (outer.attributes or {})

    async def test_empty_write_reports_zero_batch_size(self) -> None:
        """An empty write records 0, distinct from the absent one-record case."""
        provider, exporter = _provider()
        store = _store()
        store._tracer = provider.get_tracer("test")
        await store.upsert_nodes("Doc", [])
        (outer,) = [
            s
            for s in exporter.get_finished_spans()
            if s.name == "agrag.graphdb.upsert_nodes"
        ]
        assert (outer.attributes or {})["db.operation.batch.size"] == 0

    async def test_transaction_wraps_transactional_execute_write(self) -> None:
        """transaction() INTERNAL parents a transactional CLIENT write."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("test")
        store = _store()
        store._tracer = tracer
        transacted_id = uuid4()
        async with store.transaction() as tx:
            await tx.execute_write(
                "MERGE (n:Doc {id: $id})", {"id": str(transacted_id)}
            )
        spans = exporter.get_finished_spans()
        (txn,) = [s for s in spans if s.name == "agrag.graphdb.transaction"]
        assert txn.kind is SpanKind.INTERNAL
        assert txn.status.status_code is StatusCode.UNSET
        writes = [s for s in spans if s.name == "agrag.graphdb.execute_write"]
        transactional = [
            s for s in writes if (s.attributes or {}).get("agrag.transactional") is True
        ]
        assert len(transactional) == 1
        assert transactional[0].parent is not None
        assert transactional[0].parent.span_id == txn.context.span_id
        assert transactional[0].kind is SpanKind.CLIENT


class TestVectorSearchTracing:
    """vector_search missing-index path records without erroring."""

    async def test_missing_index_outer_unset_inner_error(self) -> None:
        """The outer span stays UNSET while the failed read shows ERROR."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("test")
        store = Neo4jGraphStore(
            settings=Neo4jSettings(), driver=MockDriver(), tracer=tracer
        )
        store._driver.last_session.execute_read.side_effect = RuntimeError(
            "Failed to invoke procedure `db.index.vector.queryNodes`: "
            "Caused by: java.lang.IllegalArgumentException: "
            "There is no such vector schema index: idx_0_Bogus_1_embedding"
        )
        hits = await store.vector_search(
            label="Bogus",
            vector_property="embedding",
            query_vector=[0.1, 0.2, 0.3, 0.4],
            limit=5,
        )
        assert hits == []
        spans = {span.name: span for span in exporter.get_finished_spans()}
        outer = spans["agrag.graphdb.vector_search"]
        outer_attributes = outer.attributes or {}
        assert outer_attributes["agrag.index_missing"] is True
        assert outer.status.status_code is StatusCode.UNSET
        assert len(list(outer.events)) == 1
        inner = spans["agrag.graphdb.execute_read"]
        assert inner.status.status_code is StatusCode.ERROR
        assert len(list(inner.events)) == 1
