"""Unit tests for the Qdrant vector-store backend, with a mocked client."""

import sys
from types import SimpleNamespace
from unittest import mock
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.vector_record import Distance, VectorHit, VectorRecord
from agrag.embedding.sparse_base import SparseVector
from agrag.vectordb.errors import (
    CollectionDimensionMismatchError,
    VectorStoreMissingExtraError,
)
from agrag.vectordb.qdrant import (
    _SPARSE_VECTOR_NAME,
    QdrantVectorStore,
    _min_max_normalize,
)
from agrag.vectordb.settings import QdrantSettings


class FakeQdrantClient:
    """A stand-in for AsyncQdrantClient that records calls and returns stubs."""

    def __init__(self) -> None:
        """Create the fake with async mocks for every used method."""
        self.get_collections = mock.AsyncMock()
        self.collection_exists = mock.AsyncMock(return_value=False)
        self.get_collection = mock.AsyncMock(
            return_value=make_collection_info(4, sparse=False)
        )
        self.create_collection = mock.AsyncMock(return_value=True)
        self.update_collection = mock.AsyncMock(return_value=True)
        self.upsert = mock.AsyncMock()
        self.query_points = mock.AsyncMock()
        self.scroll = mock.AsyncMock(return_value=([], None))
        self.retrieve = mock.AsyncMock(return_value=[])
        self.count = mock.AsyncMock()
        self.delete = mock.AsyncMock()
        self.delete_collection = mock.AsyncMock()
        self.close = mock.AsyncMock()


def make_point(
    point_id: str, score: float, payload: dict, vector=None
) -> SimpleNamespace:
    """Build a fake Qdrant scored point."""
    return SimpleNamespace(id=point_id, score=score, payload=payload, vector=vector)


def make_response(points: list) -> SimpleNamespace:
    """Build a fake QueryResponse around a list of points."""
    return SimpleNamespace(points=points)


def make_collection_info(size: int, *, sparse: bool = False) -> SimpleNamespace:
    """Build a fake CollectionInfo exposing a dense vector of the given size."""
    vectors = SimpleNamespace(size=size)
    sparse_vectors = {"bm25": SimpleNamespace()} if sparse else None
    config = SimpleNamespace(
        params=SimpleNamespace(vectors=vectors, sparse_vectors=sparse_vectors)
    )
    return SimpleNamespace(config=config)


@pytest.fixture
def client() -> FakeQdrantClient:
    """A fresh fake Qdrant client."""
    return FakeQdrantClient()


@pytest.fixture
def store(client: FakeQdrantClient) -> QdrantVectorStore:
    """A QdrantVectorStore backed by the fake client."""
    return QdrantVectorStore(settings=QdrantSettings(), client=client)


class TestEnsureCollection:
    """ensure_collection creates, is idempotent, and checks dimensions."""

    async def test_creates_when_absent(self, store: QdrantVectorStore, client) -> None:
        """A missing collection is created with the requested dimension."""
        await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)
        client.create_collection.assert_called_once()
        vectors_config = client.create_collection.call_args.kwargs["vectors_config"]
        assert vectors_config.size == 4
        assert (
            client.create_collection.call_args.kwargs["sparse_vectors_config"] is None
        )

    async def test_hybrid_creates_sparse_config(
        self, store: QdrantVectorStore, client
    ) -> None:
        """A hybrid collection provisions the named sparse vector and is tracked."""
        await store.ensure_collection(
            "c", dimensions=4, distance=Distance.COSINE, hybrid=True
        )
        sparse = client.create_collection.call_args.kwargs["sparse_vectors_config"]
        assert _SPARSE_VECTOR_NAME in sparse
        assert "c" in store._hybrid_collections

    async def test_non_hybrid_collection_not_tracked(
        self, store: QdrantVectorStore, client
    ) -> None:
        """A non-hybrid collection is not tracked as hybrid."""
        await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)
        assert "c" not in store._hybrid_collections

    async def test_idempotent_when_present(
        self, store: QdrantVectorStore, client
    ) -> None:
        """An existing collection with a matching dimension is not recreated."""
        client.collection_exists.return_value = True
        client.get_collection.return_value = make_collection_info(4)
        await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)
        client.create_collection.assert_not_called()

    async def test_existing_hybrid_collection_is_tracked(
        self, store: QdrantVectorStore, client
    ) -> None:
        """An already-hybrid collection is tracked without recreating it."""
        client.collection_exists.return_value = True
        client.get_collection.return_value = make_collection_info(4, sparse=True)
        await store.ensure_collection(
            "c", dimensions=4, distance=Distance.COSINE, hybrid=True
        )
        client.create_collection.assert_not_called()
        assert "c" in store._hybrid_collections

    async def test_existing_non_hybrid_collection_not_tracked(
        self, store: QdrantVectorStore, client
    ) -> None:
        """An already non-hybrid collection is not tracked as hybrid."""
        client.collection_exists.return_value = True
        client.get_collection.return_value = make_collection_info(4, sparse=False)
        await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)
        assert "c" not in store._hybrid_collections
        client.update_collection.assert_not_called()

    async def test_existing_dense_collection_upgraded_to_hybrid(
        self, store: QdrantVectorStore, client
    ) -> None:
        """Requesting hybrid on an existing dense collection adds sparse config."""
        client.collection_exists.return_value = True
        client.get_collection.return_value = make_collection_info(4, sparse=False)
        await store.ensure_collection(
            "c", dimensions=4, distance=Distance.COSINE, hybrid=True
        )
        client.update_collection.assert_called_once()
        sparse = client.update_collection.call_args.kwargs["sparse_vectors_config"]
        assert _SPARSE_VECTOR_NAME in sparse
        assert "c" in store._hybrid_collections

    async def test_upgrade_failure_does_not_mark_hybrid(
        self, store: QdrantVectorStore, client
    ) -> None:
        """A failed sparse-config upgrade leaves the collection untracked."""
        client.collection_exists.return_value = True
        client.get_collection.return_value = make_collection_info(4, sparse=False)
        client.update_collection.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            await store.ensure_collection(
                "c", dimensions=4, distance=Distance.COSINE, hybrid=True
            )
        assert "c" not in store._hybrid_collections

    async def test_dimension_mismatch_raises(
        self, store: QdrantVectorStore, client
    ) -> None:
        """A dimension conflict raises CollectionDimensionMismatchError."""
        client.collection_exists.return_value = True
        client.get_collection.return_value = make_collection_info(8)
        with pytest.raises(CollectionDimensionMismatchError) as exc_info:
            await store.ensure_collection("c", dimensions=4, distance=Distance.COSINE)
        assert exc_info.value.expected == 8
        assert exc_info.value.actual == 4

    async def test_create_failure_does_not_mark_hybrid(
        self, store: QdrantVectorStore, client
    ) -> None:
        """A failed collection creation leaves the collection untracked."""
        client.create_collection.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            await store.ensure_collection(
                "c", dimensions=4, distance=Distance.COSINE, hybrid=True
            )
        assert "c" not in store._hybrid_collections


class TestWritesAndReads:
    """upsert, search, scroll, retrieve, count, delete go through the client."""

    async def test_upsert_rejects_non_positive_batch_size(
        self, store: QdrantVectorStore, client
    ) -> None:
        """A zero or negative batch_size raises instead of silently misbehaving."""
        record = VectorRecord(id=uuid4(), vector=[0.1], payload={})
        with pytest.raises(ValueError):
            await store.upsert("c", [record], batch_size=0)
        client.upsert.assert_not_called()

    async def test_upsert_builds_points(self, store: QdrantVectorStore, client) -> None:
        """Upsert forwards id, vector, and payload as a PointStruct."""
        record = VectorRecord(id=uuid4(), vector=[0.1, 0.2], payload={"text": "a"})
        await store.upsert("c", [record])
        client.upsert.assert_called_once()
        point = client.upsert.call_args.kwargs["points"][0]
        assert point.id == str(record.id)
        assert point.vector == [0.1, 0.2]
        assert point.payload == {"text": "a"}

    async def test_upsert_attaches_sparse_vector_for_hybrid_collection(
        self, store: QdrantVectorStore, client
    ) -> None:
        """Upsert into a hybrid collection also writes a sparse vector."""
        store._hybrid_collections.add("c")
        store._checked_collections.add("c")
        sparse = mock.AsyncMock()
        sparse.embed = mock.AsyncMock(
            return_value=[SparseVector(indices=[1, 2], values=[0.5, 0.5])]
        )
        store._sparse_embedder = sparse
        record = VectorRecord(id=uuid4(), vector=[0.1, 0.2], payload={"text": "hello"})
        await store.upsert("c", [record])
        sparse.embed.assert_called_once_with(["hello"])
        point = client.upsert.call_args.kwargs["points"][0]
        assert point.vector[""] == [0.1, 0.2]
        assert point.vector[_SPARSE_VECTOR_NAME].indices == [1, 2]
        assert point.vector[_SPARSE_VECTOR_NAME].values == [0.5, 0.5]

    async def test_upsert_resolves_hybrid_state_for_unseen_collection(
        self, store: QdrantVectorStore, client
    ) -> None:
        """A fresh instance detects an already-hybrid collection on first upsert.

        Nothing here calls ensure_collection first, so this store's
        _hybrid_collections/_checked_collections start empty; the collection's
        sparse-vector support must be resolved from the backend instead of
        silently defaulting to dense.
        """
        client.get_collection.return_value = make_collection_info(4, sparse=True)
        sparse = mock.AsyncMock()
        sparse.embed = mock.AsyncMock(
            return_value=[SparseVector(indices=[1], values=[0.5])]
        )
        store._sparse_embedder = sparse
        record = VectorRecord(id=uuid4(), vector=[0.1], payload={"text": "hello"})
        await store.upsert("c", [record])
        sparse.embed.assert_called_once_with(["hello"])
        point = client.upsert.call_args.kwargs["points"][0]
        assert point.vector[_SPARSE_VECTOR_NAME].indices == [1]
        client.get_collection.assert_called_once_with("c")

        await store.upsert("c", [record])
        client.get_collection.assert_called_once_with("c")

    async def test_upsert_caches_dense_state_for_unseen_collection(
        self, store: QdrantVectorStore, client
    ) -> None:
        """A confirmed-dense collection is not re-checked on every upsert."""
        client.get_collection.return_value = make_collection_info(4, sparse=False)
        record = VectorRecord(id=uuid4(), vector=[0.1], payload={"text": "hello"})
        await store.upsert("c", [record])
        await store.upsert("c", [record])
        client.get_collection.assert_called_once_with("c")
        assert "c" not in store._hybrid_collections

    async def test_upsert_uses_empty_text_when_missing(
        self, store: QdrantVectorStore, client
    ) -> None:
        """A record with no text key still sparse-embeds, as an empty string."""
        store._hybrid_collections.add("c")
        store._checked_collections.add("c")
        sparse = mock.AsyncMock()
        sparse.embed = mock.AsyncMock(
            return_value=[SparseVector(indices=[], values=[])]
        )
        store._sparse_embedder = sparse
        record = VectorRecord(id=uuid4(), vector=[0.1], payload={"other": "field"})
        await store.upsert("c", [record])
        sparse.embed.assert_called_once_with([""])

    async def test_search_returns_hits(self, store: QdrantVectorStore, client) -> None:
        """Search maps scored points to VectorHit objects."""
        point_id = str(uuid4())
        point = make_point(point_id, 0.9, {"text": "a"})
        client.query_points.return_value = make_response([point])
        hits = await store.search("c", [0.1, 0.2], limit=5)
        assert len(hits) == 1
        assert isinstance(hits[0], VectorHit)
        assert hits[0].id == UUID(point_id)
        assert hits[0].score == 0.9

    async def test_hybrid_search_uses_sparse_embedder(
        self, store: QdrantVectorStore, client
    ) -> None:
        """hybrid_search queries dense and sparse independently, then blends."""
        sparse = mock.AsyncMock()
        sparse.embed = mock.AsyncMock(
            return_value=[SparseVector(indices=[0], values=[1.0])]
        )
        store._sparse_embedder = sparse
        point_id = str(uuid4())

        def fake_query_points(**kwargs):
            if kwargs.get("using") == _SPARSE_VECTOR_NAME:
                return make_response([make_point(point_id, 0.7, {})])
            return make_response([make_point(point_id, 0.9, {})])

        client.query_points = mock.AsyncMock(side_effect=fake_query_points)
        hits = await store.hybrid_search("c", [0.1, 0.2], "query text")
        sparse.embed.assert_called_once_with(["query text"])
        assert len(hits) == 1
        assert hits[0].id == UUID(point_id)
        assert client.query_points.call_count == 2
        sparse_call = next(
            c
            for c in client.query_points.call_args_list
            if c.kwargs.get("using") == _SPARSE_VECTOR_NAME
        )
        assert sparse_call.kwargs["query"].indices == [0]
        assert sparse_call.kwargs["query"].values == [1.0]

    async def test_hybrid_search_alpha_changes_ranking(
        self, store: QdrantVectorStore, client
    ) -> None:
        """alpha=1.0 ranks by dense only; alpha=0.0 ranks by sparse only."""
        sparse = mock.AsyncMock()
        sparse.embed = mock.AsyncMock(
            return_value=[SparseVector(indices=[0], values=[1.0])]
        )
        store._sparse_embedder = sparse
        dense_winner = str(uuid4())
        sparse_winner = str(uuid4())

        def fake_query_points(**kwargs):
            if kwargs.get("using") == _SPARSE_VECTOR_NAME:
                return make_response(
                    [
                        make_point(sparse_winner, 10.0, {}),
                        make_point(dense_winner, 1.0, {}),
                    ]
                )
            return make_response(
                [
                    make_point(dense_winner, 0.9, {}),
                    make_point(sparse_winner, 0.1, {}),
                ]
            )

        client.query_points = mock.AsyncMock(side_effect=fake_query_points)

        pure_dense = await store.hybrid_search("c", [0.1, 0.2], "q", alpha=1.0)
        assert pure_dense[0].id == UUID(dense_winner)

        pure_keyword = await store.hybrid_search("c", [0.1, 0.2], "q", alpha=0.0)
        assert pure_keyword[0].id == UUID(sparse_winner)

    async def test_scroll_returns_records_and_offset(
        self, store: QdrantVectorStore, client
    ) -> None:
        """Scroll returns the page and the next offset."""
        vector = [0.0, 0.0]
        point_id = str(uuid4())
        client.scroll.return_value = (
            [make_point(point_id, 0.0, {"text": "a"}, vector)],
            point_id,
        )
        records, offset = await store.scroll("c", limit=10, with_vectors=True)
        assert len(records) == 1
        assert records[0].id == UUID(point_id)
        assert records[0].vector == vector
        assert offset == point_id

    async def test_retrieve_returns_records(
        self, store: QdrantVectorStore, client
    ) -> None:
        """Retrieve maps fetched points to VectorRecord objects."""
        target_id = uuid4()
        client.retrieve.return_value = [
            make_point(str(target_id), 0.0, {"text": "a"}, [0.1])
        ]
        records = await store.retrieve("c", [target_id])
        assert len(records) == 1
        assert records[0].id == target_id

    async def test_retrieve_reads_dense_vector_from_hybrid_point(
        self, store: QdrantVectorStore, client
    ) -> None:
        """A hybrid point's named-vector dict yields its unnamed dense vector."""
        target_id = uuid4()
        client.retrieve.return_value = [
            make_point(
                str(target_id),
                0.0,
                {"text": "a"},
                {"": [0.1, 0.2], _SPARSE_VECTOR_NAME: SimpleNamespace()},
            )
        ]
        records = await store.retrieve("c", [target_id])
        assert records[0].vector == [0.1, 0.2]

    async def test_count_returns_total(self, store: QdrantVectorStore, client) -> None:
        """Count returns the backend count."""
        client.count.return_value = SimpleNamespace(count=3)
        assert await store.count("c") == 3

    async def test_delete_forwards_ids(self, store: QdrantVectorStore, client) -> None:
        """Delete forwards the ids to the backend."""
        target_id = uuid4()
        await store.delete("c", [target_id])
        selector = client.delete.call_args.kwargs["points_selector"]
        assert str(target_id) in selector.points

    async def test_collection_exists(self, store: QdrantVectorStore, client) -> None:
        """collection_exists forwards to the backend."""
        client.collection_exists.return_value = True
        assert await store.collection_exists("c") is True

    async def test_delete_collection(self, store: QdrantVectorStore, client) -> None:
        """delete_collection forwards to the backend."""
        await store.delete_collection("c")
        client.delete_collection.assert_called_once_with("c")

    async def test_delete_collection_clears_hybrid_tracking(
        self, store: QdrantVectorStore, client
    ) -> None:
        """Deleting a hybrid collection stops tracking it as hybrid."""
        store._hybrid_collections.add("c")
        await store.delete_collection("c")
        assert "c" not in store._hybrid_collections

    async def test_close_releases_client(
        self, store: QdrantVectorStore, client
    ) -> None:
        """Close releases the client connection."""
        await store.close()
        client.close.assert_called_once()


class TestMinMaxNormalize:
    """_min_max_normalize scales a score map to [0, 1]."""

    def test_scales_to_unit_range(self) -> None:
        """The lowest score maps to 0.0 and the highest to 1.0."""
        a, b, c = uuid4(), uuid4(), uuid4()
        result = _min_max_normalize({a: 1.0, b: 3.0, c: 5.0})
        assert result[a] == pytest.approx(0.0)
        assert result[b] == pytest.approx(0.5)
        assert result[c] == pytest.approx(1.0)

    def test_empty_input_returns_empty(self) -> None:
        """An empty score map normalizes to an empty map."""
        assert _min_max_normalize({}) == {}

    def test_tied_scores_all_normalize_to_one(self) -> None:
        """Equal scores normalize to full relevance, not a divide-by-zero."""
        a, b = uuid4(), uuid4()
        result = _min_max_normalize({a: 2.0, b: 2.0})
        assert result == {a: 1.0, b: 1.0}


class TestFuseByAlpha:
    """QdrantVectorStore._fuse_by_alpha blends dense and sparse hit lists."""

    def test_pure_dense_ignores_sparse(self) -> None:
        """alpha=1.0 ranks purely by the dense hit list."""
        dense_first, dense_second = uuid4(), uuid4()
        dense_hits = [
            VectorHit(id=dense_first, score=0.9, payload={"name": "first"}),
            VectorHit(id=dense_second, score=0.1, payload={"name": "second"}),
        ]
        sparse_hits = [
            VectorHit(id=dense_second, score=100.0, payload={"name": "second"}),
        ]
        fused = QdrantVectorStore._fuse_by_alpha(
            dense_hits, sparse_hits, alpha=1.0, limit=2
        )
        assert [hit.id for hit in fused] == [dense_first, dense_second]

    def test_pure_keyword_ignores_dense(self) -> None:
        """alpha=0.0 ranks purely by the sparse hit list."""
        dense_winner, sparse_winner = uuid4(), uuid4()
        dense_hits = [VectorHit(id=dense_winner, score=0.9, payload={})]
        sparse_hits = [
            VectorHit(id=sparse_winner, score=10.0, payload={}),
            VectorHit(id=dense_winner, score=0.1, payload={}),
        ]
        fused = QdrantVectorStore._fuse_by_alpha(
            dense_hits, sparse_hits, alpha=0.0, limit=2
        )
        assert fused[0].id == sparse_winner

    def test_missing_side_defaults_to_zero(self) -> None:
        """A hit present on only one side still ranks, weighted by alpha."""
        dense_only = uuid4()
        dense_hits = [VectorHit(id=dense_only, score=1.0, payload={"a": 1})]
        fused = QdrantVectorStore._fuse_by_alpha(dense_hits, [], alpha=0.5, limit=10)
        assert len(fused) == 1
        assert fused[0].id == dense_only
        assert fused[0].score == pytest.approx(0.5)
        assert fused[0].payload == {"a": 1}

    def test_respects_limit(self) -> None:
        """The fused result never exceeds the requested limit."""
        dense_hits = [
            VectorHit(id=uuid4(), score=float(i), payload={}) for i in range(5)
        ]
        fused = QdrantVectorStore._fuse_by_alpha(dense_hits, [], alpha=1.0, limit=2)
        assert len(fused) == 2


class TestMissingExtra:
    """Without the extra installed, use raises, not ImportError."""

    async def test_initialize_raises_missing_extra(self) -> None:
        """Initialize without qdrant-client raises VectorStoreMissingExtraError."""
        store = QdrantVectorStore()
        with (
            mock.patch.dict(sys.modules, {"qdrant_client": None}),
            pytest.raises(VectorStoreMissingExtraError) as exc_info,
        ):
            await store.initialize()
        assert exc_info.value.extra == "qdrant"
