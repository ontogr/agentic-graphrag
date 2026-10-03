"""Unit tests for the Weaviate vector-store backend, with a mocked client."""

import asyncio
from types import SimpleNamespace
from unittest import mock
from uuid import UUID, uuid4

import pytest
import weaviate
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind, StatusCode
from weaviate.classes.config import VectorDistances

from agrag.common.data_models.vector_record import Distance, VectorHit, VectorRecord
from agrag.vectordb.errors import (
    CollectionDimensionMismatchError,
    VectorStoreError,
    VectorStoreMissingExtraError,
)
from agrag.vectordb.settings import WeaviateSettings
from agrag.vectordb.weaviate import _DIMENSION_SAMPLE_PAGE_SIZE, WeaviateVectorStore


def make_batch_result(*, has_errors: bool = False, errors: dict | None = None):
    """Build a fake ``BatchObjectReturn`` from ``insert_many``."""
    return SimpleNamespace(has_errors=has_errors, errors=errors or {})


def _make_config(metric):
    """Build a fake collection config with the given distance metric."""
    index = SimpleNamespace(distance_metric=metric)
    return SimpleNamespace(
        vector_config={"vector": SimpleNamespace(vector_index_config=index)}
    )


class MockCollection:
    """A stand-in for a Weaviate collection."""

    def __init__(self) -> None:
        """Create the fake collection with async mocks for data and query."""
        self.data = SimpleNamespace(
            insert_many=mock.AsyncMock(return_value=make_batch_result()),
            delete_by_id=mock.AsyncMock(),
        )
        self.query = SimpleNamespace(
            near_vector=mock.AsyncMock(),
            hybrid=mock.AsyncMock(),
            fetch_objects=mock.AsyncMock(return_value=SimpleNamespace(objects=[])),
            fetch_object_by_id=mock.AsyncMock(),
        )
        self.aggregate = SimpleNamespace(over_all=mock.AsyncMock())
        self.config = SimpleNamespace(
            get=mock.AsyncMock(return_value=_make_config(VectorDistances.COSINE))
        )


class MockWeaviateClient:
    """A stand-in for a Weaviate async client that records calls."""

    def __init__(self) -> None:
        """Create the fake with async mocks for connection and collections."""
        self.connect = mock.AsyncMock()
        self.close = mock.AsyncMock()
        self.collections = SimpleNamespace(
            exists=mock.AsyncMock(return_value=False),
            create=mock.AsyncMock(),
        )
        self._collection = MockCollection()
        self.collections.get = lambda name: self._collection


def make_object(
    obj_id: str,
    properties: dict,
    *,
    score: float | None = None,
    distance: float | None = None,
    vector=None,
) -> SimpleNamespace:
    """Build a fake Weaviate query result object.

    ``score`` models a ``hybrid_search`` result; ``distance`` models a
    ``near_vector`` (dense-only) result, matching how the real client
    populates only the metadata field the request asked for.
    """
    return SimpleNamespace(
        uuid=obj_id,
        metadata=SimpleNamespace(score=score, distance=distance),
        properties=properties,
        vector={"vector": vector} if vector is not None else None,
    )


def make_response(objects: list) -> SimpleNamespace:
    """Build a fake query response around a list of objects."""
    return SimpleNamespace(objects=objects)


@pytest.fixture
def client() -> MockWeaviateClient:
    """A fresh fake Weaviate client."""
    return MockWeaviateClient()


@pytest.fixture
def store(client: MockWeaviateClient) -> WeaviateVectorStore:
    """A WeaviateVectorStore backed by the fake client."""
    return WeaviateVectorStore(settings=WeaviateSettings(), client=client)


class TestEnsureCollection:
    """ensure_collection creates and is idempotent."""

    async def test_new_collection_declares_every_filtered_property(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """A new collection declares the pending flag and pending job id.

        Weaviate rejects a filter on an undeclared property, and cutover
        scrolls on both.
        """
        client.collections.exists.return_value = False
        await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)
        properties = client.collections.create.call_args.kwargs["properties"]
        assert {p.name for p in properties} == {"agrag_pending", "_pending_job_id"}

    async def test_dimension_check_skips_vectorless_object_before_a_real_one(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """A vectorless object sampled first does not hide a real mismatch.

        Regression guard: checking only the first sampled object let a
        vectorless object (written by tooling other than this store) mask
        the real dimension of a vector-bearing object later in the same
        page, letting ensure_collection silently accept an incompatible
        dimension.
        """
        client.collections.exists.return_value = True
        vectorless = make_object(str(uuid4()), {})
        vector_bearing = make_object(str(uuid4()), {}, vector=[0.1] * 8)
        client._collection.query.fetch_objects.return_value = make_response(
            [vectorless, vector_bearing]
        )
        with pytest.raises(CollectionDimensionMismatchError) as exc_info:
            await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)
        assert exc_info.value.expected == 8

    async def test_dimension_check_pages_past_a_vectorless_first_page(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """A vector-bearing object on a later page is found, not just the first page.

        Regression guard: checking only the first sampled page would let a
        collection whose earliest objects are all vectorless mask a real
        dimension mismatch on a vector-bearing object further in.
        """
        client.collections.exists.return_value = True
        first_page = [
            make_object(str(uuid4()), {}) for _ in range(_DIMENSION_SAMPLE_PAGE_SIZE)
        ]
        vector_bearing = make_object(str(uuid4()), {}, vector=[0.1] * 8)

        def fake_fetch_objects(*, limit, after, include_vector):
            if after is None:
                return make_response(first_page)
            return make_response([vector_bearing])

        client._collection.query.fetch_objects = mock.AsyncMock(
            side_effect=fake_fetch_objects
        )
        with pytest.raises(CollectionDimensionMismatchError) as exc_info:
            await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)
        assert exc_info.value.expected == 8

    async def test_dimension_check_proves_no_vector_across_all_pages(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """A collection with no vector-bearing object anywhere passes silently.

        Every page is exhausted (not just the first) before concluding there
        is nothing to check.
        """
        client.collections.exists.return_value = True
        first_page = [
            make_object(str(uuid4()), {}) for _ in range(_DIMENSION_SAMPLE_PAGE_SIZE)
        ]
        second_page = [make_object(str(uuid4()), {})]

        def fake_fetch_objects(*, limit, after, include_vector):
            if after is None:
                return make_response(first_page)
            return make_response(second_page)

        client._collection.query.fetch_objects = mock.AsyncMock(
            side_effect=fake_fetch_objects
        )
        await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)
        client.collections.create.assert_not_called()
        assert client._collection.query.fetch_objects.await_count == 2


class TestWritesAndReads:
    """upsert, search, hybrid_search, scroll, retrieve, count, delete."""

    async def test_upsert_rejects_non_positive_batch_size(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """A zero or negative batch_size raises instead of silently misbehaving."""
        record = VectorRecord(id=uuid4(), vector=[0.1], payload={})
        with pytest.raises(ValueError):
            await store.upsert("c", [record], batch_size=-1)
        client._collection.data.insert_many.assert_not_called()

    async def test_upsert_rejects_payload_reserved_for_pending_metadata(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """Payload cannot overwrite the metadata field that controls visibility."""
        record = VectorRecord(
            id=uuid4(), vector=[0.1], payload={"agrag_pending": "user value"}
        )

        with pytest.raises(ValueError, match="reserved for internal use"):
            await store.upsert("c", [record])

        client._collection.data.insert_many.assert_not_called()

    async def test_upsert_batches_large_writes(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """Upsert issues one insert_many call per batch_size chunk."""
        records = [VectorRecord(id=uuid4(), vector=[0.1], payload={}) for _ in range(5)]
        await store.upsert("c", records, batch_size=2)
        insert_many = client._collection.data.insert_many
        assert insert_many.call_count == 3
        assert [len(c.args[0]) for c in insert_many.call_args_list] == [2, 2, 1]

    async def test_upsert_raises_on_batch_errors(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """A batch reporting errors raises instead of silently dropping records."""
        client._collection.data.insert_many.return_value = make_batch_result(
            has_errors=True, errors={0: "boom"}
        )
        record = VectorRecord(id=uuid4(), vector=[0.1], payload={})
        with pytest.raises(VectorStoreError):
            await store.upsert("c", [record])

    @pytest.mark.parametrize(
        ("metric", "distance", "expected"),
        [
            (VectorDistances.COSINE, 0.1, 0.9),
            (VectorDistances.L2_SQUARED, 0.1, -0.1),
            (VectorDistances.DOT, -0.7, 0.7),
        ],
    )
    async def test_search_returns_hits(
        self, store: WeaviateVectorStore, client, metric, distance, expected
    ) -> None:
        """Search maps a near_vector distance to a higher-is-closer score."""
        obj_id = str(uuid4())
        obj = make_object(obj_id, {"text": "a"}, distance=distance)
        client._collection.config.get.return_value = _make_config(metric)
        client._collection.query.near_vector.return_value = make_response([obj])
        hits = await store.search("c", [0.1, 0.2], limit=5)
        assert len(hits) == 1
        assert isinstance(hits[0], VectorHit)
        assert hits[0].id == UUID(obj_id)
        assert hits[0].score == pytest.approx(expected)

    async def test_search_rejects_non_positive_limit(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """A non-positive limit raises instead of reaching the backend."""
        with pytest.raises(ValueError, match="positive"):
            await store.search("c", [0.1, 0.2], limit=0)
        client._collection.query.near_vector.assert_not_called()

    async def test_hybrid_search_rejects_invalid_alpha(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """An out-of-range alpha raises instead of reaching the backend."""
        with pytest.raises(ValueError, match="0.0 and 1.0"):
            await store.hybrid_search("c", [0.1, 0.2], "q", alpha=1.5)
        client._collection.query.hybrid.assert_not_called()

    async def test_scroll_returns_records_and_offset(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """Scroll returns the page and the next numeric offset."""
        obj_id = str(uuid4())
        obj = make_object(obj_id, {"text": "a"}, vector=[0.1])
        client._collection.query.fetch_objects.return_value = make_response([obj])
        records, offset = await store.scroll("c", limit=1, with_vectors=True)
        assert len(records) == 1
        assert records[0].id == UUID(obj_id)
        assert records[0].vector == [0.1]
        assert offset == "1"

    async def test_scroll_zero_limit_returns_empty_page(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """limit=0 returns an empty page instead of crashing on an empty index.

        Regression guard: ``len(objects) == limit`` was true for an empty
        result at ``limit=0``, so indexing ``objects[-1]`` raised
        ``IndexError`` instead of signaling there is no next page.
        """
        client._collection.query.fetch_objects.return_value = make_response([])
        records, offset = await store.scroll("c", limit=0)
        assert records == []
        assert offset is None

    async def test_delete_forwards_ids(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """Delete forwards each id to the backend."""
        target_id = uuid4()
        await store.delete("c", [target_id])
        client._collection.data.delete_by_id.assert_called_once_with(
            uuid=str(target_id)
        )


class TestEnsureClientMode:
    """_ensure_client builds the right client for each configured mode."""

    async def test_cloud_mode_builds_cloud_client(self) -> None:
        """mode="cloud" builds a Weaviate Cloud client."""
        mock_client = mock.AsyncMock()
        with mock.patch.object(
            weaviate, "use_async_with_weaviate_cloud", return_value=mock_client
        ) as build:
            store = WeaviateVectorStore(
                settings=WeaviateSettings(
                    mode="cloud", url="https://xyz.cloud.weaviate.io"
                )
            )
            client = await store._ensure_client()
        build.assert_called_once()
        assert build.call_args.kwargs["cluster_url"] == "https://xyz.cloud.weaviate.io"
        mock_client.connect.assert_called_once()
        assert client is mock_client

    async def test_default_settings_build_custom_client(self) -> None:
        """Default settings (custom mode, localhost URL) build a custom client.

        Regression guard: the default mode used to be "cloud" paired with a
        localhost default URL, so an out-of-the-box store tried the cloud
        connector against a local instance instead of the custom one.
        """
        mock_client = mock.AsyncMock()
        with mock.patch.object(
            weaviate, "use_async_with_custom", return_value=mock_client
        ) as build:
            store = WeaviateVectorStore(settings=WeaviateSettings())
            client = await store._ensure_client()
        build.assert_called_once()
        assert client is mock_client

    async def test_custom_mode_maps_secure_nondefault_endpoint(self) -> None:
        """Custom mode maps a secure, non-default endpoint to client settings."""
        mock_client = mock.AsyncMock()
        with mock.patch.object(
            weaviate, "use_async_with_custom", return_value=mock_client
        ) as build:
            store = WeaviateVectorStore(
                settings=WeaviateSettings(
                    mode="custom",
                    url="https://weaviate.example.test:8443",
                    grpc_port=50052,
                )
            )
            await store._ensure_client()
        build.assert_called_once_with(
            http_host="weaviate.example.test",
            http_port=8443,
            http_secure=True,
            grpc_host="weaviate.example.test",
            grpc_port=50052,
            grpc_secure=True,
            auth_credentials=None,
        )

    async def test_concurrent_first_calls_connect_once(self) -> None:
        """Concurrent first calls share one connect, not a disconnected client.

        Regression guard: assigning ``self._client`` before awaiting
        ``connect()`` let a second concurrent caller observe and use a
        still-disconnected client.
        """
        mock_client = mock.AsyncMock()

        async def slow_connect() -> None:
            await asyncio.sleep(0)

        mock_client.connect.side_effect = slow_connect
        with mock.patch.object(
            weaviate, "use_async_with_weaviate_cloud", return_value=mock_client
        ) as build:
            store = WeaviateVectorStore(
                settings=WeaviateSettings(
                    mode="cloud", url="https://xyz.cloud.weaviate.io"
                )
            )
            first, second = await asyncio.gather(
                store._ensure_client(), store._ensure_client()
            )
        build.assert_called_once()
        mock_client.connect.assert_called_once()
        assert first is mock_client
        assert second is mock_client

    async def test_failed_connect_is_retried_on_next_call(self) -> None:
        """A failed connect leaves ``self._client`` unset so the next call retries."""
        failing_client = mock.AsyncMock()
        failing_client.connect.side_effect = RuntimeError("boom")
        working_client = mock.AsyncMock()
        with mock.patch.object(
            weaviate,
            "use_async_with_weaviate_cloud",
            side_effect=[failing_client, working_client],
        ):
            store = WeaviateVectorStore(
                settings=WeaviateSettings(
                    mode="cloud", url="https://xyz.cloud.weaviate.io"
                )
            )
            with pytest.raises(RuntimeError):
                await store._ensure_client()
            assert store._client is None
            client = await store._ensure_client()
        assert client is working_client
        working_client.connect.assert_called_once()

    async def test_failed_connect_closes_the_abandoned_client(self) -> None:
        """A failed connect closes the local client instead of leaking it.

        Regression guard: each retry after a connect failure built a new
        HTTP/gRPC client without ever closing the one abandoned by the
        previous failed attempt, leaking a pair of unclosed connections per
        retry.
        """
        failing_client = mock.AsyncMock()
        failing_client.connect.side_effect = RuntimeError("boom")
        with mock.patch.object(
            weaviate, "use_async_with_weaviate_cloud", return_value=failing_client
        ):
            store = WeaviateVectorStore(
                settings=WeaviateSettings(
                    mode="cloud", url="https://xyz.cloud.weaviate.io"
                )
            )
            with pytest.raises(RuntimeError):
                await store._ensure_client()
        failing_client.close.assert_called_once()

    async def test_close_failure_does_not_mask_connect_error(self) -> None:
        """If cleanup close() also fails, the original connect error still raises."""
        failing_client = mock.AsyncMock()
        failing_client.connect.side_effect = RuntimeError("connect boom")
        failing_client.close.side_effect = RuntimeError("close boom")
        with mock.patch.object(
            weaviate, "use_async_with_weaviate_cloud", return_value=failing_client
        ):
            store = WeaviateVectorStore(
                settings=WeaviateSettings(
                    mode="cloud", url="https://xyz.cloud.weaviate.io"
                )
            )
            with pytest.raises(RuntimeError, match="connect boom"):
                await store._ensure_client()


class TestMissingExtra:
    """Without the extra installed, use raises, not ImportError."""

    async def test_initialize_raises_missing_extra(self) -> None:
        """Initialize without weaviate-client raises VectorStoreMissingExtraError."""
        store = WeaviateVectorStore()
        with (
            mock.patch.dict("sys.modules", {"weaviate": None}),
            pytest.raises(VectorStoreMissingExtraError) as exc_info,
        ):
            await store.initialize()
        assert exc_info.value.extra == "weaviate"


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
        store = WeaviateVectorStore(
            settings=WeaviateSettings(),
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
            assert (batch.attributes or {}).get("db.system.name") == "weaviate"
            assert (batch.attributes or {}).get("db.collection.name") == "c"
            assert batch.parent is not None
            assert batch.parent.span_id == outer.context.span_id
            assert batch.status.status_code is StatusCode.UNSET

    async def test_upsert_error_marks_outer_error_batch_unset(self, client) -> None:
        """A failing Weaviate batch raises outside its span: outer is ERROR.

        Weaviate checks ``has_errors`` after the per-batch CLIENT span has
        already closed, so the batch span stays UNSET while the outer
        ``upsert`` span — where the ``VectorStoreError`` actually raises —
        is ERROR. This matches the plan's behavioral note for Weaviate's
        raise-on-first-batch-error path.
        """
        provider, exporter = _provider()
        store = WeaviateVectorStore(
            settings=WeaviateSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        client._collection.data.insert_many.return_value = make_batch_result(
            has_errors=True, errors={0: "boom"}
        )
        record = VectorRecord(id=uuid4(), vector=[0.1], payload={})
        with pytest.raises(VectorStoreError):
            await store.upsert("c", [record])
        spans = {s.name: s for s in exporter.get_finished_spans()}
        assert spans["agrag.vectordb.upsert_batch"].status.status_code is (
            StatusCode.UNSET
        )
        assert spans["agrag.vectordb.upsert"].status.status_code is (StatusCode.ERROR)
        assert len(list(spans["agrag.vectordb.upsert"].events)) == 1


class TestTracingSearch:
    """Traced search/hybrid export one CLIENT span with query attributes."""

    async def test_search_span_carries_system_collection_limit(self, client) -> None:
        """Search exports one CLIENT span with system, collection, limit."""
        provider, exporter = _provider()
        store = WeaviateVectorStore(
            settings=WeaviateSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        obj_id = str(uuid4())
        obj = make_object(obj_id, {"text": "a"}, distance=0.1)
        client._collection.query.near_vector.return_value = make_response([obj])
        hits = await store.search("c", [0.1, 0.2], limit=5)
        assert len(hits) == 1
        (span,) = [
            s
            for s in exporter.get_finished_spans()
            if s.name == "agrag.vectordb.search"
        ]
        assert span.kind is SpanKind.CLIENT
        assert (span.attributes or {})["db.system.name"] == "weaviate"
        assert (span.attributes or {})["db.collection.name"] == "c"
        assert (span.attributes or {})["agrag.limit"] == 5
        assert span.status.status_code is StatusCode.UNSET

    async def test_search_error_marks_span_error(self, client) -> None:
        """A failing search marks its span ERROR with one exception event."""
        provider, exporter = _provider()
        store = WeaviateVectorStore(
            settings=WeaviateSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        client._collection.query.near_vector = mock.AsyncMock(
            side_effect=RuntimeError("down")
        )
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
        store = WeaviateVectorStore(
            settings=WeaviateSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        obj_id = str(uuid4())
        obj = make_object(obj_id, {"text": "a"}, score=0.9)
        client._collection.query.hybrid.return_value = make_response([obj])
        hits = await store.hybrid_search("c", [0.1, 0.2], "query", limit=5, alpha=0.6)
        assert len(hits) == 1
        (span,) = [
            s
            for s in exporter.get_finished_spans()
            if s.name == "agrag.vectordb.hybrid_search"
        ]
        assert span.kind is SpanKind.CLIENT
        assert (span.attributes or {})["db.system.name"] == "weaviate"
        assert (span.attributes or {})["db.collection.name"] == "c"
        assert (span.attributes or {})["agrag.limit"] == 5
        assert (span.attributes or {})["agrag.alpha"] == 0.6
        assert span.status.status_code is StatusCode.UNSET


class TestTracingDirectCalls:
    """Traced scroll/retrieve/count/delete each export one CLIENT span."""

    async def test_scroll_span_carries_system_collection_limit(self, client) -> None:
        """Scroll exports one CLIENT span with system, collection, limit."""
        provider, exporter = _provider()
        store = WeaviateVectorStore(
            settings=WeaviateSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        obj_id = str(uuid4())
        client._collection.query.fetch_objects.return_value = make_response(
            [make_object(obj_id, {"text": "a"})]
        )
        records, next_offset = await store.scroll("c", limit=1)
        assert len(records) == 1
        assert next_offset == "1"
        (span,) = [
            s
            for s in exporter.get_finished_spans()
            if s.name == "agrag.vectordb.scroll"
        ]
        assert span.kind is SpanKind.CLIENT
        attributes = span.attributes or {}
        assert attributes["db.system.name"] == "weaviate"
        assert attributes["db.collection.name"] == "c"
        assert attributes["agrag.limit"] == 1
        assert span.status.status_code is StatusCode.UNSET

    async def test_retrieve_exports_one_span_per_id(self, client) -> None:
        """Retrieve exports one CLIENT span per id round trip."""
        provider, exporter = _provider()
        store = WeaviateVectorStore(
            settings=WeaviateSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        obj_id = uuid4()
        client._collection.query.fetch_object_by_id.return_value = make_object(
            str(obj_id), {"text": "a"}, vector=[0.1]
        )
        records = await store.retrieve("c", [obj_id])
        assert len(records) == 1
        spans = [
            s
            for s in exporter.get_finished_spans()
            if s.name == "agrag.vectordb.retrieve"
        ]
        assert len(spans) == 1
        span = spans[0]
        assert span.kind is SpanKind.CLIENT
        attributes = span.attributes or {}
        assert attributes["db.system.name"] == "weaviate"
        assert attributes["db.collection.name"] == "c"
        assert span.status.status_code is StatusCode.UNSET

    async def test_count_span_carries_system_and_collection(self, client) -> None:
        """Count exports one CLIENT span with system and collection."""
        provider, exporter = _provider()
        store = WeaviateVectorStore(
            settings=WeaviateSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        client._collection.aggregate.over_all.return_value = SimpleNamespace(
            total_count=3
        )
        assert await store.count("c") == 3
        (span,) = [
            s for s in exporter.get_finished_spans() if s.name == "agrag.vectordb.count"
        ]
        assert span.kind is SpanKind.CLIENT
        attributes = span.attributes or {}
        assert attributes["db.system.name"] == "weaviate"
        assert attributes["db.collection.name"] == "c"
        assert span.status.status_code is StatusCode.UNSET

    async def test_delete_span_carries_system_and_collection(self, client) -> None:
        """Delete exports one CLIENT span with system and collection."""
        provider, exporter = _provider()
        store = WeaviateVectorStore(
            settings=WeaviateSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        await store.delete("c", [uuid4()])
        (span,) = [
            s
            for s in exporter.get_finished_spans()
            if s.name == "agrag.vectordb.delete"
        ]
        assert span.kind is SpanKind.CLIENT
        attributes = span.attributes or {}
        assert attributes["db.system.name"] == "weaviate"
        assert attributes["db.collection.name"] == "c"
        assert span.status.status_code is StatusCode.UNSET

    async def test_failing_count_marks_span_error(self, client) -> None:
        """A failing count marks its span ERROR with one exception event."""
        provider, exporter = _provider()
        store = WeaviateVectorStore(
            settings=WeaviateSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        client._collection.aggregate.over_all = mock.AsyncMock(
            side_effect=RuntimeError("down")
        )
        with pytest.raises(RuntimeError, match="down"):
            await store.count("c")
        (span,) = [
            s for s in exporter.get_finished_spans() if s.name == "agrag.vectordb.count"
        ]
        assert span.status.status_code is StatusCode.ERROR
        assert len(list(span.events)) == 1


class TestTracingBuildClient:
    """Concurrent first use exports exactly one build_client span."""

    async def test_concurrent_first_calls_export_single_build_span(
        self,
    ) -> None:
        """Two concurrent _ensure_client calls share one INTERNAL span."""
        provider, exporter = _provider()
        store = WeaviateVectorStore(
            settings=WeaviateSettings(
                mode="cloud", url="https://xyz.cloud.weaviate.io"
            ),
            tracer=provider.get_tracer("test"),
        )
        mock_client = mock.AsyncMock()
        with mock.patch.object(
            weaviate, "use_async_with_weaviate_cloud", return_value=mock_client
        ):
            first, second = await asyncio.gather(
                store._ensure_client(), store._ensure_client()
            )
        assert first is mock_client
        assert second is mock_client
        mock_client.connect.assert_called_once()
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
        store = WeaviateVectorStore(
            settings=WeaviateSettings(), client=client, tracer=None
        )
        record = VectorRecord(id=uuid4(), vector=[0.1], payload={"text": "a"})
        with host_tracer.start_as_current_span("host.request"):
            await store.upsert("c", [record])
        (host_span,) = exporter.get_finished_spans()
        assert host_span.name == "host.request"
        assert host_span.status.status_code is StatusCode.UNSET
        assert list(host_span.events) == []
