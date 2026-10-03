"""Unit tests for the Milvus vector-store backend, with a mocked client."""

import asyncio
from types import SimpleNamespace
from unittest import mock
from uuid import UUID, uuid4

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind, StatusCode
from pymilvus.exceptions import MilvusException

from agrag.common.data_models.vector_record import Distance, VectorHit, VectorRecord
from agrag.vectordb.errors import (
    VectorStoreError,
    VectorStoreMissingExtraError,
)
from agrag.vectordb.milvus import (
    MAX_RESPONSE_LIMIT,
    MilvusVectorStore,
    _escape_list,
    _escape_scalar,
)
from agrag.vectordb.settings import MilvusSettings


_ALL_ADAPTER_FIELDS = ["id", "vector", "text", "sparse", "payload", "pending"]


def _describe_collection(dim: int = 4, *, fields: list[str] | None = None) -> dict:
    """Build a fake ``describe_collection`` response.

    Args:
        dim: The dense vector field's dimension.
        fields: The field names the collection carries. Defaults to this
        adapter's full required set, including the pending marker,
            representing a collection this adapter can actually serve.
    """
    field_names = _ALL_ADAPTER_FIELDS if fields is None else fields
    return {
        "fields": [
            {"name": name, "params": {"dim": dim} if name == "vector" else {}}
            for name in field_names
        ]
    }


class MockMilvusClient:
    """A stand-in for AsyncMilvusClient that records calls and returns stubs."""

    def __init__(self) -> None:
        """Create the fake with async mocks for every used method."""
        self.list_collections = mock.AsyncMock(return_value=[])
        self.has_collection = mock.AsyncMock(return_value=False)
        self.describe_collection = mock.AsyncMock(return_value=_describe_collection())
        self.describe_index = mock.AsyncMock(return_value={"metric_type": "COSINE"})
        self.drop_collection = mock.AsyncMock()
        self.prepare_index_params = mock.MagicMock(
            return_value=SimpleNamespace(add_index=mock.MagicMock())
        )
        self.create_collection = mock.AsyncMock()
        self.add_collection_field = mock.AsyncMock()
        self.load_collection = mock.AsyncMock()
        self.upsert = mock.AsyncMock()
        self.search = mock.AsyncMock(return_value=[[{"id": "x", "distance": 0.9}]])
        self.hybrid_search = mock.AsyncMock(
            return_value=[[{"id": "x", "distance": 0.8}]]
        )
        self.query = mock.AsyncMock(return_value=[])
        self.get = mock.AsyncMock(return_value=[])
        self.delete = mock.AsyncMock()
        self.close = mock.AsyncMock()


@pytest.fixture
def client() -> MockMilvusClient:
    """A fresh fake Milvus client."""
    return MockMilvusClient()


@pytest.fixture
def store(client: MockMilvusClient) -> MilvusVectorStore:
    """A MilvusVectorStore backed by the fake client."""
    return MilvusVectorStore(settings=MilvusSettings(), client=client)


class TestEnsureCollection:
    """ensure_collection creates and is idempotent."""

    async def test_concurrent_stores_create_collection_once(self, client) -> None:
        """Store instances share provisioning state for the same collection."""
        first_create_started = asyncio.Event()
        allow_first_create = asyncio.Event()
        collection_exists = False

        async def has_collection(name: str) -> bool:
            return collection_exists

        async def create_collection(**kwargs) -> None:
            nonlocal collection_exists
            first_create_started.set()
            await allow_first_create.wait()
            if collection_exists:
                raise MilvusException(message="collection already exists")
            collection_exists = True

        client.has_collection.side_effect = has_collection
        client.create_collection.side_effect = create_collection
        first_store = MilvusVectorStore(settings=MilvusSettings(), client=client)
        second_store = MilvusVectorStore(settings=MilvusSettings(), client=client)

        first_task = asyncio.create_task(
            first_store.ensure_collection(
                "concurrent", dimensions=4, distance=Distance.COSINE
            )
        )
        await first_create_started.wait()
        second_task = asyncio.create_task(
            second_store.ensure_collection(
                "concurrent", dimensions=4, distance=Distance.COSINE
            )
        )
        allow_first_create.set()
        await asyncio.gather(first_task, second_task)

        client.create_collection.assert_called_once()
        client.load_collection.assert_called_once_with("concurrent")

    async def test_accepts_collection_created_by_another_process(
        self, store: MilvusVectorStore, client
    ) -> None:
        """A duplicate-create response is valid when the resulting schema is valid."""
        client.has_collection.side_effect = [False, True]
        client.create_collection.side_effect = MilvusException(
            message="collection already exists"
        )

        await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)

        client.load_collection.assert_not_called()

    async def test_existing_dense_only_collection_raises(
        self, store: MilvusVectorStore, client
    ) -> None:
        """An existing collection with only id/vector fields is rejected.

        Regression guard: upsert and hybrid_search always read and write the
        text, sparse, and payload fields (Milvus has no per-call hybrid
        toggle), so a dense-only collection this adapter did not provision
        would fail at write or search time instead of at setup time.
        """
        client.has_collection.return_value = True
        client.describe_collection.return_value = _describe_collection(
            dim=4, fields=["id", "vector"]
        )
        with pytest.raises(VectorStoreError, match="missing fields"):
            await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)

    async def test_existing_collection_migrates_pending_schema(
        self, store: MilvusVectorStore, client
    ) -> None:
        """An older collection gains the pending field and index in place."""
        client.has_collection.return_value = True
        client.describe_collection.return_value = _describe_collection(
            dim=4, fields=[field for field in _ALL_ADAPTER_FIELDS if field != "pending"]
        )

        async def fake_describe_index(*, collection_name: str, index_name: str):
            if index_name == "pending":
                raise MilvusException("index not found")
            return {"metric_type": "BM25"}

        client.describe_index = mock.AsyncMock(side_effect=fake_describe_index)
        client.add_collection_field = mock.AsyncMock()
        client.create_index = mock.AsyncMock()

        await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)

        client.add_collection_field.assert_awaited_once_with(
            collection_name="c",
            field_name="pending",
            data_type=mock.ANY,
            nullable=True,
            default_value=False,
        )
        client.create_index.assert_awaited_once()
        assert client.create_index.call_args.kwargs["collection_name"] == "c"

    async def test_existing_collection_missing_sparse_index_raises(
        self, store: MilvusVectorStore, client
    ) -> None:
        """An existing collection with every field but no sparse index is rejected.

        Regression guard: hybrid_search issues an AnnSearchRequest against
        the sparse field's index; without that index the field exists but
        cannot actually be searched.
        """
        client.has_collection.return_value = True
        client.describe_collection.return_value = _describe_collection(dim=4)

        async def fake_describe_index(*, collection_name: str, index_name: str):
            if index_name == "sparse":
                raise MilvusException("index not found")
            return {"metric_type": "COSINE"}

        client.describe_index = mock.AsyncMock(side_effect=fake_describe_index)
        with pytest.raises(VectorStoreError, match="sparse index present: False"):
            await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)


class TestWritesAndReads:
    """upsert, search, hybrid_search, scroll, retrieve, count, delete."""

    async def test_upsert_rejects_non_positive_batch_size(
        self, store: MilvusVectorStore, client
    ) -> None:
        """A zero or negative batch_size raises instead of silently misbehaving."""
        record = VectorRecord(id=uuid4(), vector=[0.1], payload={})
        with pytest.raises(ValueError):
            await store.upsert("c", [record], batch_size=0)
        client.upsert.assert_not_called()

    async def test_upsert_normalizes_non_json_native_values(
        self, store: MilvusVectorStore, client
    ) -> None:
        """A UUID payload value is stringified before writing, as it was before."""
        payload_uuid = uuid4()
        record = VectorRecord(id=uuid4(), vector=[0.1], payload={"ref": payload_uuid})
        await store.upsert("c", [record])
        row = client.upsert.call_args.kwargs["data"][0]
        assert row["payload"] == {"ref": str(payload_uuid)}

    async def test_search_returns_hits(self, store: MilvusVectorStore, client) -> None:
        """Search maps rows to VectorHit objects."""
        obj_id = str(uuid4())
        client.search.return_value = [
            [{"id": obj_id, "distance": 0.9, "payload": {"text": "a"}}]
        ]
        hits = await store.search("c", [0.1, 0.2], limit=5)
        assert len(hits) == 1
        assert isinstance(hits[0], VectorHit)
        assert hits[0].id == UUID(obj_id)
        assert hits[0].score == 0.9
        assert hits[0].payload == {"text": "a"}

    async def test_search_rejects_non_positive_limit(
        self, store: MilvusVectorStore, client
    ) -> None:
        """A non-positive limit raises instead of reaching the backend."""
        with pytest.raises(ValueError, match="positive"):
            await store.search("c", [0.1, 0.2], limit=0)
        client.search.assert_not_called()

    async def test_hybrid_search_rejects_invalid_alpha(
        self, store: MilvusVectorStore, client
    ) -> None:
        """An out-of-range alpha raises instead of reaching the backend."""
        with pytest.raises(ValueError, match="0.0 and 1.0"):
            await store.hybrid_search("c", [0.1, 0.2], "q", alpha=-0.1)
        client.hybrid_search.assert_not_called()

    async def test_search_inverts_euclidean_distance(
        self, store: MilvusVectorStore, client
    ) -> None:
        """An L2 collection's raw distance is negated so higher is closer."""
        client.describe_index.return_value = {"metric_type": "L2"}
        obj_id = str(uuid4())
        client.search.return_value = [[{"id": obj_id, "distance": 0.5}]]
        hits = await store.search("c", [0.1, 0.2], limit=5)
        assert hits[0].score == pytest.approx(-0.5)

    async def test_search_keeps_cosine_distance_as_is(
        self, store: MilvusVectorStore, client
    ) -> None:
        """A COSINE collection's distance field is already a similarity score."""
        client.describe_index.return_value = {"metric_type": "COSINE"}
        obj_id = str(uuid4())
        client.search.return_value = [[{"id": obj_id, "distance": 0.5}]]
        hits = await store.search("c", [0.1, 0.2], limit=5)
        assert hits[0].score == pytest.approx(0.5)

    async def test_scroll_returns_records_and_offset(
        self, store: MilvusVectorStore, client
    ) -> None:
        """Scroll returns the page and the next id cursor when the page is full."""
        obj_id = str(uuid4())
        client.query.return_value = [{"id": obj_id, "vector": [0.1], "payload": {}}]
        records, offset = await store.scroll("c", limit=1, with_vectors=True)
        assert len(records) == 1
        assert records[0].vector == [0.1]
        assert offset == obj_id

    async def test_scroll_never_sends_offset(
        self, store: MilvusVectorStore, client
    ) -> None:
        """Scroll never sends a numeric offset, regardless of page depth.

        Regression guard: Milvus rejects a query whose offset + limit
        exceeds MAX_RESPONSE_LIMIT, so a numeric offset cannot page past
        that many total records without eventually erroring and leaving
        later records unread. The id cursor needs no offset at all.
        """
        obj_id = str(uuid4())
        client.query.return_value = [{"id": obj_id, "vector": [0.1], "payload": {}}]
        await store.scroll("c", limit=1, page_offset=str(uuid4()))
        assert "offset" not in client.query.call_args.kwargs

    async def test_scroll_filters_on_id_cursor(
        self, store: MilvusVectorStore, client
    ) -> None:
        """A follow-up page filters on ``id > page_offset``, combined with filters."""
        cursor = str(uuid4())
        client.query.return_value = []
        await store.scroll("c", limit=10, page_offset=cursor, filters={"kind": "a"})
        expr = client.query.call_args.kwargs["filter"]
        assert f"id > {_escape_scalar(cursor)}" in expr
        assert 'payload["kind"] == "a"' in expr

    async def test_scroll_next_offset_is_last_row_id_in_order(
        self, store: MilvusVectorStore, client
    ) -> None:
        """The next cursor is the last (highest) id in the ordered page."""
        ids = [str(uuid4()) for _ in range(2)]
        client.query.return_value = [
            {"id": i, "vector": [], "payload": {}} for i in ids
        ]
        _, offset = await store.scroll("c", limit=2)
        assert offset == ids[-1]

    async def test_scroll_zero_limit_returns_empty_page(
        self, store: MilvusVectorStore, client
    ) -> None:
        """limit=0 returns an empty page instead of crashing on an empty result.

        Regression guard: ``len(rows) == safe_limit`` was true for an empty
        result at ``limit=0``, so indexing ``rows[-1]`` raised ``IndexError``
        instead of signaling there is no next page.
        """
        client.query.return_value = []
        records, offset = await store.scroll("c", limit=0)
        assert records == []
        assert offset is None

    async def test_scroll_caps_response_limit(
        self, store: MilvusVectorStore, client
    ) -> None:
        """Scroll caps the page size at MAX_RESPONSE_LIMIT."""
        big = MAX_RESPONSE_LIMIT + 10
        await store.scroll("c", limit=big)
        assert client.query.call_args.kwargs["limit"] == MAX_RESPONSE_LIMIT

    async def test_retrieve_preserves_order(
        self, store: MilvusVectorStore, client
    ) -> None:
        """Retrieve returns records in the requested id order, omitting misses."""
        first, second = uuid4(), uuid4()
        client.get.return_value = [
            {"id": str(second), "vector": [0.1], "payload": {}},
            {"id": str(first), "vector": [0.2], "payload": {}},
        ]
        records = await store.retrieve("c", [first, second])
        assert [r.id for r in records] == [first, second]

    async def test_retrieve_batches_large_id_lists(
        self, store: MilvusVectorStore, client
    ) -> None:
        """Retrieve chunks a large id list instead of sending it all in one call.

        Regression guard: a single request covering too many ids can exceed
        Milvus's cloud response cap; MAX_RESPONSE_LIMIT already documents
        that retrieve is meant to chunk the same way scroll does.
        """
        ids = [uuid4() for _ in range(MAX_RESPONSE_LIMIT + 5)]
        client.get.return_value = []
        await store.retrieve("c", ids)
        assert client.get.call_count == 2
        first_batch = client.get.call_args_list[0].kwargs["ids"]
        second_batch = client.get.call_args_list[1].kwargs["ids"]
        assert len(first_batch) == MAX_RESPONSE_LIMIT
        assert len(second_batch) == 5

    async def test_delete_forwards_ids(self, store: MilvusVectorStore, client) -> None:
        """Delete forwards the ids to the backend."""
        target_id = uuid4()
        await store.delete("c", [target_id])
        assert client.delete.call_args.kwargs["ids"] == [str(target_id)]


class TestFilterEscaping:
    """The Milvus filter expression builder must resist injection."""

    def test_scalar_escapes_quotes(self) -> None:
        """A quote in a string value is escaped, not emitted raw."""
        assert _escape_scalar('a"b') == '"a\\"b"'

    def test_scalar_escapes_backslash(self) -> None:
        """A backslash in a string value is escaped."""
        assert _escape_scalar("a\\b") == '"a\\\\b"'

    def test_scalar_bool_lowercased(self) -> None:
        """A bool renders as Milvus's lower-case literal."""
        assert _escape_scalar(True) == "true"
        assert _escape_scalar(False) == "false"

    def test_list_builds_in_clause(self) -> None:
        """A list value builds a bracketed, escaped ``in`` clause body."""
        assert _escape_list(["a", "b"]) == '["a", "b"]'

    def test_compile_rejects_bad_field(self) -> None:
        """A filter key that is not an identifier raises ValueError."""
        store = MilvusVectorStore(settings=MilvusSettings())
        with pytest.raises(ValueError):
            store._compile_filter({"bad field; drop": "x"})

    def test_compile_neutralizes_operator_in_value(self) -> None:
        """An operator-looking value stays inside an escaped literal."""
        store = MilvusVectorStore(settings=MilvusSettings())
        expr = store._compile_filter({"kind": 'x" or 1==1'})
        assert 'payload["kind"] == "x\\" or 1==1"' in expr


class TestMissingExtra:
    """Without the extra installed, use raises, not ImportError."""

    async def test_initialize_raises_missing_extra(self) -> None:
        """Initialize without pymilvus raises VectorStoreMissingExtraError."""
        store = MilvusVectorStore()
        with (
            mock.patch.dict("sys.modules", {"pymilvus": None}),
            pytest.raises(VectorStoreMissingExtraError) as exc_info,
        ):
            await store.initialize()
        assert exc_info.value.extra == "milvus"


class TestEnsureClientConcurrency:
    """_ensure_client serializes concurrent first calls."""

    async def test_concurrent_first_calls_build_client_once(self) -> None:
        """Concurrent first calls build exactly one Milvus client, not one each."""
        build_calls = 0

        def mock_client_ctor(*args, **kwargs):
            nonlocal build_calls
            build_calls += 1
            return object()

        store = MilvusVectorStore(settings=MilvusSettings())
        with mock.patch("pymilvus.AsyncMilvusClient", side_effect=mock_client_ctor):
            first, second = await asyncio.gather(
                store._ensure_client(), store._ensure_client()
            )
        assert build_calls == 1
        assert first is second


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Return a provider wired to an in-memory exporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


class TestTracingUpsert:
    """Traced upsert exports one outer span plus one child per batch."""

    async def test_upsert_exports_one_outer_plus_n_batch_spans(self, client) -> None:
        """Five records at batch_size=2 export 1 outer INTERNAL + 3 CLIENT."""
        provider, exporter = _provider()
        store = MilvusVectorStore(
            settings=MilvusSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        records = [VectorRecord(id=uuid4(), vector=[0.1], payload={}) for _ in range(5)]
        await store.upsert("c", records, batch_size=2)

        by_name: dict[str, list] = {}
        for span in exporter.get_finished_spans():
            by_name.setdefault(span.name, []).append(span)
        (outer,) = by_name["agrag.vectordb.upsert"]
        assert outer.kind is SpanKind.INTERNAL
        assert (outer.attributes or {}).get("db.collection.name") == "c"
        assert (outer.attributes or {})["agrag.record_count"] == 5
        assert outer.status.status_code is StatusCode.UNSET
        batches = by_name["agrag.vectordb.upsert_batch"]
        assert len(batches) == 3
        assert [b.attributes["agrag.batch_size"] for b in batches] == [2, 2, 1]
        for batch in batches:
            assert batch.kind is SpanKind.CLIENT
            assert (batch.attributes or {}).get("db.system.name") == "milvus"
            assert (batch.attributes or {}).get("db.collection.name") == "c"
            assert batch.parent is not None
            assert batch.parent.span_id == outer.context.span_id
            assert batch.status.status_code is StatusCode.UNSET

    async def test_upsert_error_marks_batch_and_outer_error(self, client) -> None:
        """A failing batch marks both the batch span and outer span ERROR."""
        provider, exporter = _provider()
        store = MilvusVectorStore(
            settings=MilvusSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        client.upsert = mock.AsyncMock(side_effect=RuntimeError("boom"))
        record = VectorRecord(id=uuid4(), vector=[0.1], payload={})
        with pytest.raises(RuntimeError, match="boom"):
            await store.upsert("c", [record])
        spans = {s.name: s for s in exporter.get_finished_spans()}
        assert spans["agrag.vectordb.upsert_batch"].status.status_code is (
            StatusCode.ERROR
        )
        assert len(list(spans["agrag.vectordb.upsert_batch"].events)) == 1
        assert spans["agrag.vectordb.upsert"].status.status_code is (StatusCode.ERROR)


class TestTracingSearch:
    """Traced search/hybrid export one CLIENT span with query attributes."""

    async def test_search_span_carries_system_collection_limit(self, client) -> None:
        """Search exports one CLIENT span with system, collection, limit."""
        provider, exporter = _provider()
        store = MilvusVectorStore(
            settings=MilvusSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        obj_id = str(uuid4())
        client.search.return_value = [[{"id": obj_id, "distance": 0.9, "payload": {}}]]
        hits = await store.search("c", [0.1, 0.2], limit=5)
        assert len(hits) == 1
        (span,) = [
            s
            for s in exporter.get_finished_spans()
            if s.name == "agrag.vectordb.search"
        ]
        assert span.kind is SpanKind.CLIENT
        assert (span.attributes or {})["db.system.name"] == "milvus"
        assert (span.attributes or {})["db.collection.name"] == "c"
        assert (span.attributes or {})["agrag.limit"] == 5
        assert span.status.status_code is StatusCode.UNSET

    async def test_search_error_marks_span_error(self, client) -> None:
        """A failing search marks its span ERROR with one exception event."""
        provider, exporter = _provider()
        store = MilvusVectorStore(
            settings=MilvusSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        client.search = mock.AsyncMock(side_effect=RuntimeError("down"))
        with pytest.raises(RuntimeError, match="down"):
            await store.search("c", [0.1, 0.2], limit=5)
        (span,) = [
            s
            for s in exporter.get_finished_spans()
            if s.name == "agrag.vectordb.search"
        ]
        assert span.status.status_code is StatusCode.ERROR
        assert len(list(span.events)) == 1

    async def test_hybrid_search_single_client_span(self, client) -> None:
        """Hybrid exports a single CLIENT span with limit and alpha."""
        provider, exporter = _provider()
        store = MilvusVectorStore(
            settings=MilvusSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        obj_id = str(uuid4())
        client.hybrid_search.return_value = [[{"id": obj_id, "distance": 0.8}]]
        hits = await store.hybrid_search("c", [0.1, 0.2], "query", limit=5, alpha=0.6)
        assert len(hits) == 1
        (span,) = [
            s
            for s in exporter.get_finished_spans()
            if s.name == "agrag.vectordb.hybrid_search"
        ]
        assert span.kind is SpanKind.CLIENT
        assert (span.attributes or {})["db.system.name"] == "milvus"
        assert (span.attributes or {})["db.collection.name"] == "c"
        assert (span.attributes or {})["agrag.limit"] == 5
        assert (span.attributes or {})["agrag.alpha"] == 0.6
        assert span.status.status_code is StatusCode.UNSET


class TestTracingDirectCalls:
    """Traced scroll/retrieve/count/delete each export one CLIENT span."""

    async def test_scroll_span_carries_system_collection_limit(self, client) -> None:
        """Scroll exports one CLIENT span with system, collection, limit."""
        provider, exporter = _provider()
        store = MilvusVectorStore(
            settings=MilvusSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        records, next_offset = await store.scroll("c", limit=7)
        assert records == []
        assert next_offset is None
        (span,) = exporter.get_finished_spans()
        assert span.name == "agrag.vectordb.scroll"
        assert span.kind is SpanKind.CLIENT
        attributes = span.attributes or {}
        assert attributes["db.system.name"] == "milvus"
        assert attributes["db.collection.name"] == "c"
        assert attributes["agrag.limit"] == 7
        assert span.status.status_code is StatusCode.UNSET

    async def test_retrieve_exports_one_span_per_id_batch(self, client) -> None:
        """Retrieve exports one CLIENT span per batched round trip."""
        provider, exporter = _provider()
        store = MilvusVectorStore(
            settings=MilvusSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        ids = [uuid4() for _ in range(MAX_RESPONSE_LIMIT + 5)]
        client.get.return_value = []
        await store.retrieve("c", ids)
        spans = [
            span
            for span in exporter.get_finished_spans()
            if span.name == "agrag.vectordb.retrieve"
        ]
        assert len(spans) == 2
        for span in spans:
            assert span.kind is SpanKind.CLIENT
            attributes = span.attributes or {}
            assert attributes["db.system.name"] == "milvus"
            assert attributes["db.collection.name"] == "c"
            assert span.status.status_code is StatusCode.UNSET

    async def test_count_span_carries_system_and_collection(self, client) -> None:
        """Count exports one CLIENT span with system and collection."""
        provider, exporter = _provider()
        store = MilvusVectorStore(
            settings=MilvusSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        client.query.return_value = [{"count(*)": 3}]
        assert await store.count("c") == 3
        (span,) = exporter.get_finished_spans()
        assert span.name == "agrag.vectordb.count"
        assert span.kind is SpanKind.CLIENT
        attributes = span.attributes or {}
        assert attributes["db.system.name"] == "milvus"
        assert attributes["db.collection.name"] == "c"
        assert span.status.status_code is StatusCode.UNSET

    async def test_delete_span_carries_system_and_collection(self, client) -> None:
        """Delete exports one CLIENT span with system and collection."""
        provider, exporter = _provider()
        store = MilvusVectorStore(
            settings=MilvusSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        await store.delete("c", [uuid4()])
        (span,) = exporter.get_finished_spans()
        assert span.name == "agrag.vectordb.delete"
        assert span.kind is SpanKind.CLIENT
        attributes = span.attributes or {}
        assert attributes["db.system.name"] == "milvus"
        assert attributes["db.collection.name"] == "c"
        assert span.status.status_code is StatusCode.UNSET

    async def test_failing_delete_marks_span_error(self, client) -> None:
        """A failing delete marks its span ERROR with one exception event."""
        provider, exporter = _provider()
        store = MilvusVectorStore(
            settings=MilvusSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        client.delete = mock.AsyncMock(side_effect=RuntimeError("down"))
        with pytest.raises(RuntimeError, match="down"):
            await store.delete("c", [uuid4()])
        (span,) = exporter.get_finished_spans()
        assert span.name == "agrag.vectordb.delete"
        assert span.status.status_code is StatusCode.ERROR
        assert len(list(span.events)) == 1


class TestTracingBuildClient:
    """Concurrent first use exports exactly one build_client span."""

    async def test_concurrent_first_calls_export_single_build_span(
        self,
    ) -> None:
        """Two concurrent _ensure_client calls share one INTERNAL span."""
        provider, exporter = _provider()
        store = MilvusVectorStore(
            settings=MilvusSettings(), tracer=provider.get_tracer("test")
        )
        build_calls = 0

        def mock_client_ctor(*args, **kwargs):
            nonlocal build_calls
            build_calls += 1
            return object()

        with mock.patch("pymilvus.AsyncMilvusClient", side_effect=mock_client_ctor):
            first, second = await asyncio.gather(
                store._ensure_client(), store._ensure_client()
            )
        assert build_calls == 1
        assert first is second
        builds = [
            s
            for s in exporter.get_finished_spans()
            if s.name == "agrag.vectordb.build_client"
        ]
        assert len(builds) == 1
        assert builds[0].kind is SpanKind.INTERNAL


class TestTracingDisabled:
    """A store built without a tracer never marks a host span."""

    async def test_tracer_none_leaves_host_span_unset(self, client) -> None:
        """The host span stays UNSET with no events under tracer=None."""
        provider, exporter = _provider()
        host_tracer = provider.get_tracer("host")
        store = MilvusVectorStore(settings=MilvusSettings(), client=client, tracer=None)
        record = VectorRecord(id=uuid4(), vector=[0.1], payload={"text": "a"})
        with host_tracer.start_as_current_span("host.request"):
            await store.upsert("c", [record])
        (host_span,) = exporter.get_finished_spans()
        assert host_span.name == "host.request"
        assert host_span.status.status_code is StatusCode.UNSET
        assert list(host_span.events) == []
