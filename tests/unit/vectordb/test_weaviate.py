"""Unit tests for the Weaviate vector-store backend, with a mocked client."""

from types import SimpleNamespace
from unittest import mock
from uuid import UUID, uuid4

import pytest
import weaviate

from agrag.common.data_models.vector_record import Distance, VectorHit, VectorRecord
from agrag.vectordb.errors import VectorStoreMissingExtraError
from agrag.vectordb.settings import WeaviateSettings
from agrag.vectordb.weaviate import WeaviateVectorStore


class FakeCollection:
    """A stand-in for a Weaviate collection."""

    def __init__(self) -> None:
        """Create the fake collection with async mocks for data and query."""
        self.data = SimpleNamespace(
            insert=mock.AsyncMock(),
            delete_by_id=mock.AsyncMock(),
        )
        self.query = SimpleNamespace(
            near_vector=mock.AsyncMock(),
            hybrid=mock.AsyncMock(),
            fetch_objects=mock.AsyncMock(),
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
    obj_id: str, score: float, properties: dict, vector=None
) -> SimpleNamespace:
    """Build a fake Weaviate query result object."""
    return SimpleNamespace(
        uuid=obj_id,
        metadata=SimpleNamespace(score=score),
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


class TestWritesAndReads:
    """upsert, search, hybrid_search, scroll, retrieve, count, delete."""

    async def test_upsert_inserts_objects(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """Upsert inserts each record with its vector under the vector name."""
        record = VectorRecord(id=uuid4(), vector=[0.1, 0.2], payload={"text": "a"})
        await store.upsert("c", [record])
        insert = client._collection.data.insert
        insert.assert_called_once()
        kwargs = insert.call_args.kwargs
        assert kwargs["properties"] == {"text": "a"}
        assert kwargs["vector"] == {"vector": [0.1, 0.2]}
        assert kwargs["uuid"] == str(record.id)

    async def test_search_returns_hits(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """Search maps objects to VectorHit objects."""
        obj_id = str(uuid4())
        obj = make_object(obj_id, 0.9, {"text": "a"})
        client._collection.query.near_vector.return_value = make_response([obj])
        hits = await store.search("c", [0.1, 0.2], limit=5)
        assert len(hits) == 1
        assert isinstance(hits[0], VectorHit)
        assert hits[0].id == UUID(obj_id)
        assert hits[0].score == 0.9

    async def test_hybrid_search_passes_text_and_vector(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """hybrid_search forwards the text and dense vector to the backend."""
        obj_id = str(uuid4())
        obj = make_object(obj_id, 0.8, {})
        client._collection.query.hybrid.return_value = make_response([obj])
        hits = await store.hybrid_search("c", [0.1, 0.2], "query text", alpha=0.3)
        assert len(hits) == 1
        assert hits[0].id == UUID(obj_id)
        kwargs = client._collection.query.hybrid.call_args.kwargs
        assert kwargs["query"] == "query text"
        assert kwargs["vector"] == [0.1, 0.2]
        assert kwargs["alpha"] == 0.3

    async def test_scroll_returns_records_and_offset(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """Scroll returns the page and the next cursor."""
        obj_id = str(uuid4())
        obj = make_object(obj_id, 0.0, {"text": "a"}, [0.1])
        client._collection.query.fetch_objects.return_value = make_response([obj])
        records, offset = await store.scroll("c", limit=1, with_vectors=True)
        assert len(records) == 1
        assert records[0].id == UUID(obj_id)
        assert records[0].vector == [0.1]
        assert offset == obj_id

    async def test_retrieve_returns_records(
        self, store: WeaviateVectorStore, client
    ) -> None:
        """Retrieve maps the fetched object to a VectorRecord."""
        target_id = uuid4()
        client._collection.query.fetch_object_by_id.return_value = make_object(
            str(target_id), 0.0, {"text": "a"}, [0.1]
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
        """mode="cloud" (the default) builds a Weaviate Cloud client."""
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
