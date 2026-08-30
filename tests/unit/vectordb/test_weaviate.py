"""Unit tests for the Weaviate vector-store backend, with a mocked client."""

import asyncio
from types import SimpleNamespace
from unittest import mock
from uuid import UUID, uuid4

import pytest
import weaviate

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


class FakeCollection:
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
        self.aggregate = SimpleNamespace(count=mock.AsyncMock())


class FakeWeaviateClient:
    """A stand-in for a Weaviate async client that records calls."""

    def __init__(self) -> None:
        """Create the fake with async mocks for connection and collections."""
        self.connect = mock.AsyncMock()
        self.close = mock.AsyncMock()
        self.collections = SimpleNamespace(
            exists=mock.AsyncMock(return_value=False),
            create=mock.AsyncMock(),
        )
        self._collection = FakeCollection()
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
def client() -> FakeWeaviateClient:
    """A fresh fake Weaviate client."""
    return FakeWeaviateClient()


@pytest.fixture
def store(client: FakeWeaviateClient) -> WeaviateVectorStore:
    """A WeaviateVectorStore backed by the fake client."""
    return WeaviateVectorStore(settings=WeaviateSettings(), client=client)


class TestEnsureCollection:
    """ensure_collection creates and is idempotent."""

    async def test_creates_when_absent(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """A missing collection is created with the requested distance."""
        await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)
        client.collections.create.assert_called_once()
        assert client.collections.create.call_args.kwargs["name"] == "c"

    async def test_idempotent_when_present(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """An existing collection is not recreated."""
        client.collections.exists.return_value = True
        await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)
        client.collections.create.assert_not_called()

    async def test_dimension_mismatch_raises(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """A sample object's vector length conflicting with dimensions raises."""
        client.collections.exists.return_value = True
        client._collection.query.fetch_objects.return_value = make_response(
            [make_object(str(uuid4()), {}, vector=[0.1] * 8)]
        )
        with pytest.raises(CollectionDimensionMismatchError) as exc_info:
            await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)
        assert exc_info.value.expected == 8
        assert exc_info.value.actual == 4

    async def test_dimension_match_does_not_raise(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """A sample object's vector length matching dimensions passes silently."""
        client.collections.exists.return_value = True
        client._collection.query.fetch_objects.return_value = make_response(
            [make_object(str(uuid4()), {}, vector=[0.1] * 4)]
        )
        await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)
        client.collections.create.assert_not_called()

    async def test_empty_existing_collection_not_checked(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """An existing but empty collection has nothing to check, so it passes."""
        client.collections.exists.return_value = True
        client._collection.query.fetch_objects.return_value = make_response([])
        await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)
        client.collections.create.assert_not_called()

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

    async def test_upsert_inserts_objects(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """Upsert batch-inserts each record with its vector under the vector name."""
        record = VectorRecord(id=uuid4(), vector=[0.1, 0.2], payload={"text": "a"})
        await store.upsert("c", [record])
        insert_many = client._collection.data.insert_many
        insert_many.assert_called_once()
        [obj] = insert_many.call_args.args[0]
        assert obj.properties == {"text": "a"}
        assert obj.vector == {"vector": [0.1, 0.2]}
        assert obj.uuid == str(record.id)

    async def test_upsert_rejects_non_positive_batch_size(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """A zero or negative batch_size raises instead of silently misbehaving."""
        record = VectorRecord(id=uuid4(), vector=[0.1], payload={})
        with pytest.raises(ValueError):
            await store.upsert("c", [record], batch_size=-1)
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

    async def test_search_returns_hits(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """Search maps a near_vector distance to a higher-is-closer score."""
        obj_id = str(uuid4())
        obj = make_object(obj_id, {"text": "a"}, distance=0.1)
        client._collection.query.near_vector.return_value = make_response([obj])
        hits = await store.search("c", [0.1, 0.2], limit=5)
        assert len(hits) == 1
        assert isinstance(hits[0], VectorHit)
        assert hits[0].id == UUID(obj_id)
        assert hits[0].score == pytest.approx(-0.1)

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

    async def test_hybrid_search_passes_text_and_vector(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """hybrid_search forwards the text and dense vector to the backend."""
        obj_id = str(uuid4())
        obj = make_object(obj_id, {}, score=0.8)
        client._collection.query.hybrid.return_value = make_response([obj])
        hits = await store.hybrid_search("c", [0.1, 0.2], "query text", alpha=0.3)
        assert len(hits) == 1
        assert hits[0].id == UUID(obj_id)
        assert hits[0].score == 0.8
        kwargs = client._collection.query.hybrid.call_args.kwargs
        assert kwargs["query"] == "query text"
        assert kwargs["vector"] == [0.1, 0.2]
        assert kwargs["alpha"] == 0.3

    async def test_scroll_returns_records_and_offset(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """Scroll returns the page and the next cursor."""
        obj_id = str(uuid4())
        obj = make_object(obj_id, {"text": "a"}, vector=[0.1])
        client._collection.query.fetch_objects.return_value = make_response([obj])
        records, offset = await store.scroll("c", limit=1, with_vectors=True)
        assert len(records) == 1
        assert records[0].id == UUID(obj_id)
        assert records[0].vector == [0.1]
        assert offset == obj_id

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

    async def test_retrieve_returns_records(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """Retrieve maps the fetched object to a VectorRecord."""
        target_id = uuid4()
        client._collection.query.fetch_object_by_id.return_value = make_object(
            str(target_id), {"text": "a"}, vector=[0.1]
        )
        records = await store.retrieve("c", [target_id])
        assert len(records) == 1
        assert records[0].id == target_id

    async def test_count_returns_total(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """Count returns the backend total."""
        client._collection.aggregate.count.return_value = SimpleNamespace(total_count=3)
        assert await store.count("c") == 3

    async def test_delete_forwards_ids(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """Delete forwards each id to the backend."""
        target_id = uuid4()
        await store.delete("c", [target_id])
        client._collection.data.delete_by_id.assert_called_once_with(
            uuid=str(target_id)
        )

    async def test_close_releases_client(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """Close releases the client connection."""
        await store.close()
        client.close.assert_called_once()


class TestEnsureClientMode:
    """_ensure_client builds the right client for each configured mode."""

    async def test_cloud_mode_builds_cloud_client(self) -> None:
        """mode="cloud" builds a Weaviate Cloud client."""
        fake_client = mock.AsyncMock()
        with mock.patch.object(
            weaviate, "use_async_with_weaviate_cloud", return_value=fake_client
        ) as build:
            store = WeaviateVectorStore(
                settings=WeaviateSettings(
                    mode="cloud", url="https://xyz.cloud.weaviate.io"
                )
            )
            client = await store._ensure_client()
        build.assert_called_once()
        assert build.call_args.kwargs["cluster_url"] == "https://xyz.cloud.weaviate.io"
        fake_client.connect.assert_called_once()
        assert client is fake_client

    async def test_default_settings_build_custom_client(self) -> None:
        """Default settings (custom mode, localhost URL) build a custom client.

        Regression guard: the default mode used to be "cloud" paired with a
        localhost default URL, so an out-of-the-box store tried the cloud
        connector against a local instance instead of the custom one.
        """
        fake_client = mock.AsyncMock()
        with mock.patch.object(
            weaviate, "use_async_with_custom", return_value=fake_client
        ) as build:
            store = WeaviateVectorStore(settings=WeaviateSettings())
            client = await store._ensure_client()
        build.assert_called_once()
        assert client is fake_client

    async def test_custom_mode_builds_custom_client(self) -> None:
        """mode="custom" parses the URL and builds a self-hosted client."""
        fake_client = mock.AsyncMock()
        with mock.patch.object(
            weaviate, "use_async_with_custom", return_value=fake_client
        ) as build:
            store = WeaviateVectorStore(
                settings=WeaviateSettings(mode="custom", url="http://localhost:8080")
            )
            client = await store._ensure_client()
        build.assert_called_once()
        assert build.call_args.kwargs["http_host"] == "localhost"
        assert build.call_args.kwargs["http_port"] == 8080
        assert build.call_args.kwargs["http_secure"] is False
        fake_client.connect.assert_called_once()
        assert client is fake_client

    async def test_concurrent_first_calls_connect_once(self) -> None:
        """Concurrent first calls share one connect, not a disconnected client.

        Regression guard: assigning ``self._client`` before awaiting
        ``connect()`` let a second concurrent caller observe and use a
        still-disconnected client.
        """
        fake_client = mock.AsyncMock()

        async def slow_connect() -> None:
            await asyncio.sleep(0)

        fake_client.connect.side_effect = slow_connect
        with mock.patch.object(
            weaviate, "use_async_with_weaviate_cloud", return_value=fake_client
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
        fake_client.connect.assert_called_once()
        assert first is fake_client
        assert second is fake_client

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
