"""Unit tests for the Qdrant vector-store backend, with a mocked client."""

import asyncio
import sys
from types import SimpleNamespace
from typing import Any
from unittest import mock
from uuid import UUID, uuid4

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind, StatusCode
from qdrant_client import models as qdrant_models

from agrag.common.data_models.vector_record import Distance, VectorHit, VectorRecord
from agrag.embedding.sparse_base import SparseVector
from agrag.vectordb.errors import VectorStoreMissingExtraError
from agrag.vectordb.qdrant import (
    _SPARSE_VECTOR_NAME,
    QdrantVectorStore,
    _min_max_normalize,
)
from agrag.vectordb.settings import QdrantSettings


class MockQdrantClient:
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


def make_collection_info(
    size: int,
    *,
    sparse: bool = False,
    sparse_name: str = _SPARSE_VECTOR_NAME,
    distance: Any = None,
) -> SimpleNamespace:
    """Build a fake CollectionInfo exposing a dense vector of the given size.

    ``sparse_name`` lets a test simulate a collection carrying some other
    application's sparse vector under a different name, which must not be
    mistaken for this store's own named ``bm25`` vector.
    """
    vectors = SimpleNamespace(size=size, distance=distance)
    sparse_vectors = {sparse_name: SimpleNamespace()} if sparse else None
    config = SimpleNamespace(
        params=SimpleNamespace(vectors=vectors, sparse_vectors=sparse_vectors)
    )
    return SimpleNamespace(config=config)


@pytest.fixture
def client() -> MockQdrantClient:
    """A fresh fake Qdrant client."""
    return MockQdrantClient()


@pytest.fixture
def store(client: MockQdrantClient) -> QdrantVectorStore:
    """A QdrantVectorStore backed by the fake client."""
    return QdrantVectorStore(settings=QdrantSettings(), client=client)


class TestEnsureCollection:
    """ensure_collection creates, is idempotent, and checks dimensions."""

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

    async def test_upsert_does_not_treat_unrelated_sparse_vector_as_bm25(
        self, store: QdrantVectorStore, client
    ) -> None:
        """A collection's unrelated sparse vector does not trigger sparse-embedding.

        Regression guard: checking only "does sparse_vectors exist" would
        treat any other application's differently-named sparse vector as if
        it were this store's own ``bm25`` field, sparse-embedding records
        into a collection that has no ``bm25`` field to hold them.
        """
        client.get_collection.return_value = make_collection_info(
            4, sparse=True, sparse_name="some_other_app_vector"
        )
        sparse = mock.AsyncMock()
        store._sparse_embedder = sparse
        record = VectorRecord(id=uuid4(), vector=[0.1], payload={"text": "hello"})
        await store.upsert("c", [record])
        sparse.embed.assert_not_called()
        assert "c" not in store._hybrid_collections

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

    async def test_search_rejects_non_positive_limit(
        self, store: QdrantVectorStore, client
    ) -> None:
        """A non-positive limit raises instead of reaching the backend."""
        with pytest.raises(ValueError, match="positive"):
            await store.search("c", [0.1, 0.2], limit=0)
        client.query_points.assert_not_called()

    async def test_hybrid_search_rejects_invalid_alpha(
        self, store: QdrantVectorStore, client
    ) -> None:
        """An out-of-range alpha raises instead of reaching the backend."""
        with pytest.raises(ValueError, match="0.0 and 1.0"):
            await store.hybrid_search("c", [0.1, 0.2], "q", alpha=1.5)
        client.query_points.assert_not_called()

    async def test_search_inverts_score_for_euclidean_collection(
        self, store: QdrantVectorStore, client
    ) -> None:
        """A Euclidean collection's raw distance is negated to higher-is-closer.

        Regression guard: Qdrant reports literal Euclidean distance (lower is
        closer) for EUCLID collections, unlike COSINE/DOT where the score is
        already a similarity. VectorHit.score must stay higher-is-closer
        regardless of the collection's distance metric.
        """
        client.get_collection.return_value = make_collection_info(
            4, distance=qdrant_models.Distance.EUCLID
        )
        point_id = str(uuid4())
        point = make_point(point_id, 0.4, {})
        client.query_points.return_value = make_response([point])
        hits = await store.search("c", [0.1, 0.2], limit=5)
        assert hits[0].score == -0.4

    async def test_hybrid_search_inverts_dense_score_for_euclidean_collection(
        self, store: QdrantVectorStore, client
    ) -> None:
        """Pure-dense fusion ranks by distance, not raw score, for EUCLID collections.

        Regression guard: without inverting the dense arm's raw Euclidean
        distance before fusion, the farthest (worst) dense match would
        normalize to the highest blended score and win pure-dense ranking.
        """
        client.get_collection.return_value = make_collection_info(
            4, distance=qdrant_models.Distance.EUCLID
        )
        sparse = mock.AsyncMock()
        sparse.query_embed = mock.AsyncMock(
            return_value=[SparseVector(indices=[0], values=[1.0])]
        )
        store._sparse_embedder = sparse
        near = str(uuid4())
        far = str(uuid4())

        def fake_query_points(**kwargs):
            if kwargs.get("using") == _SPARSE_VECTOR_NAME:
                return make_response([])
            # Euclidean distance: smaller is a closer match.
            return make_response([make_point(near, 0.1, {}), make_point(far, 5.0, {})])

        client.query_points = mock.AsyncMock(side_effect=fake_query_points)
        hits = await store.hybrid_search("c", [0.1, 0.2], "query text", alpha=1.0)
        assert hits[0].id == UUID(near)

    async def test_hybrid_search_alpha_changes_ranking(
        self, store: QdrantVectorStore, client
    ) -> None:
        """alpha=1.0 ranks by dense only; alpha=0.0 ranks by sparse only."""
        sparse = mock.AsyncMock()
        sparse.query_embed = mock.AsyncMock(
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

    def test_pure_keyword_excludes_dense_only_candidates(self) -> None:
        """A dense-only hit with no keyword match is excluded at alpha=0.0.

        Regression guard: a candidate absent from the sparse pool defaults to
        a 0.0 contribution, the same normalized score the worst real sparse
        hit can get, so before this fix a dense-only hit could tie into and
        fill a result slot a pure keyword search should reserve for real
        keyword matches.
        """
        dense_only = uuid4()
        sparse_winner = uuid4()
        dense_hits = [VectorHit(id=dense_only, score=0.9, payload={})]
        sparse_hits = [VectorHit(id=sparse_winner, score=10.0, payload={})]
        fused = QdrantVectorStore._fuse_by_alpha(
            dense_hits, sparse_hits, alpha=0.0, limit=5
        )
        assert [hit.id for hit in fused] == [sparse_winner]

    def test_pure_dense_excludes_sparse_only_candidates(self) -> None:
        """A sparse-only hit with no dense match is excluded at alpha=1.0."""
        sparse_only = uuid4()
        dense_winner = uuid4()
        dense_hits = [VectorHit(id=dense_winner, score=0.9, payload={})]
        sparse_hits = [VectorHit(id=sparse_only, score=10.0, payload={})]
        fused = QdrantVectorStore._fuse_by_alpha(
            dense_hits, sparse_hits, alpha=1.0, limit=5
        )
        assert [hit.id for hit in fused] == [dense_winner]

    def test_missing_side_defaults_to_zero(self) -> None:
        """A hit present on only one side still ranks, weighted by alpha."""
        dense_only = uuid4()
        dense_hits = [VectorHit(id=dense_only, score=1.0, payload={"a": 1})]
        fused = QdrantVectorStore._fuse_by_alpha(dense_hits, [], alpha=0.5, limit=10)
        assert len(fused) == 1
        assert fused[0].id == dense_only
        assert fused[0].score == pytest.approx(0.5)
        assert fused[0].payload == {"a": 1}


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


class TestEnsureClientConcurrency:
    """_ensure_client serializes concurrent first calls."""

    async def test_concurrent_first_calls_build_client_once(self) -> None:
        """Concurrent first calls build exactly one Qdrant client, not one each."""
        build_calls = 0

        def mock_client_ctor(*args, **kwargs):
            nonlocal build_calls
            build_calls += 1
            return object()

        store = QdrantVectorStore(settings=QdrantSettings())
        with mock.patch(
            "qdrant_client.AsyncQdrantClient", side_effect=mock_client_ctor
        ):
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
        store = QdrantVectorStore(
            settings=QdrantSettings(),
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
            assert (batch.attributes or {}).get("db.system.name") == "qdrant"
            assert (batch.attributes or {}).get("db.collection.name") == "c"
            assert batch.parent is not None
            assert batch.parent.span_id == outer.context.span_id
            assert batch.status.status_code is StatusCode.UNSET


class TestTracingSearch:
    """Traced search/hybrid export connected spans with query attributes."""

    async def test_search_span_carries_system_collection_limit(self, client) -> None:
        """Search exports one CLIENT span with system, collection, limit."""
        provider, exporter = _provider()
        store = QdrantVectorStore(
            settings=QdrantSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        point_id = str(uuid4())
        client.query_points.return_value = make_response(
            [make_point(point_id, 0.9, {})]
        )
        hits = await store.search("c", [0.1, 0.2], limit=5)
        assert len(hits) == 1
        (span,) = [
            s
            for s in exporter.get_finished_spans()
            if s.name == "agrag.vectordb.search"
        ]
        assert span.kind is SpanKind.CLIENT
        assert (span.attributes or {})["db.system.name"] == "qdrant"
        assert (span.attributes or {})["db.collection.name"] == "c"
        assert (span.attributes or {})["agrag.limit"] == 5
        assert span.status.status_code is StatusCode.UNSET

    async def test_hybrid_outer_internal_with_dense_sparse_arms(self, client) -> None:
        """Hybrid exports one INTERNAL outer with dense/sparse CLIENT arms."""
        provider, exporter = _provider()
        store = QdrantVectorStore(
            settings=QdrantSettings(),
            client=client,
            tracer=provider.get_tracer("test"),
        )
        sparse = mock.AsyncMock()
        sparse.query_embed = mock.AsyncMock(
            return_value=[SparseVector(indices=[0], values=[1.0])]
        )
        store._sparse_embedder = sparse
        point_id = str(uuid4())

        async def fake_query_points(**kwargs):
            if kwargs.get("using") == _SPARSE_VECTOR_NAME:
                return make_response([make_point(point_id, 0.7, {})])
            return make_response([make_point(point_id, 0.9, {})])

        client.query_points = mock.AsyncMock(side_effect=fake_query_points)
        hits = await store.hybrid_search(
            "c", [0.1, 0.2], "query text", limit=5, alpha=0.6
        )
        assert len(hits) == 1
        spans = exporter.get_finished_spans()
        (outer,) = [s for s in spans if s.name == "agrag.vectordb.hybrid_search"]
        assert outer.kind is SpanKind.INTERNAL
        assert (outer.attributes or {})["agrag.limit"] == 5
        assert (outer.attributes or {})["agrag.alpha"] == 0.6
        assert outer.status.status_code is StatusCode.UNSET
        arms = [s for s in spans if s.name == "agrag.vectordb.query_points"]
        assert len(arms) == 2
        assert {(a.attributes or {})["agrag.query_arm"] for a in arms} == {
            "dense",
            "sparse",
        }
        for arm in arms:
            assert arm.kind is SpanKind.CLIENT
            assert (arm.attributes or {})["db.system.name"] == "qdrant"
            assert arm.parent is not None
            assert arm.parent.span_id == outer.context.span_id


class TestTracingDirectCalls:
    """Traced scroll/retrieve/count/delete each export one CLIENT span."""

    async def test_scroll_span_carries_system_collection_limit(self, client) -> None:
        """Scroll exports one CLIENT span with system, collection, limit."""
        provider, exporter = _provider()
        store = QdrantVectorStore(
            settings=QdrantSettings(),
            client=client,
            models=qdrant_models,
            tracer=provider.get_tracer("test"),
        )
        records, next_offset = await store.scroll("c", limit=7)
        assert records == []
        assert next_offset is None
        (span,) = exporter.get_finished_spans()
        assert span.name == "agrag.vectordb.scroll"
        assert span.kind is SpanKind.CLIENT
        attributes = span.attributes or {}
        assert attributes["db.system.name"] == "qdrant"
        assert attributes["db.collection.name"] == "c"
        assert attributes["agrag.limit"] == 7
        assert span.status.status_code is StatusCode.UNSET

    async def test_retrieve_span_carries_system_and_collection(self, client) -> None:
        """Retrieve exports one CLIENT span with system and collection."""
        provider, exporter = _provider()
        store = QdrantVectorStore(
            settings=QdrantSettings(),
            client=client,
            models=qdrant_models,
            tracer=provider.get_tracer("test"),
        )
        await store.retrieve("c", [uuid4()])
        (span,) = exporter.get_finished_spans()
        assert span.name == "agrag.vectordb.retrieve"
        assert span.kind is SpanKind.CLIENT
        attributes = span.attributes or {}
        assert attributes["db.system.name"] == "qdrant"
        assert attributes["db.collection.name"] == "c"
        assert span.status.status_code is StatusCode.UNSET

    async def test_count_span_carries_system_and_collection(self, client) -> None:
        """Count exports one CLIENT span with system and collection."""
        provider, exporter = _provider()
        store = QdrantVectorStore(
            settings=QdrantSettings(),
            client=client,
            models=qdrant_models,
            tracer=provider.get_tracer("test"),
        )
        client.count.return_value = SimpleNamespace(count=3)
        assert await store.count("c") == 3
        (span,) = exporter.get_finished_spans()
        assert span.name == "agrag.vectordb.count"
        assert span.kind is SpanKind.CLIENT
        attributes = span.attributes or {}
        assert attributes["db.system.name"] == "qdrant"
        assert attributes["db.collection.name"] == "c"
        assert span.status.status_code is StatusCode.UNSET

    async def test_delete_span_carries_system_and_collection(self, client) -> None:
        """Delete exports one CLIENT span with system and collection."""
        provider, exporter = _provider()
        store = QdrantVectorStore(
            settings=QdrantSettings(),
            client=client,
            models=qdrant_models,
            tracer=provider.get_tracer("test"),
        )
        await store.delete("c", [uuid4()])
        (span,) = exporter.get_finished_spans()
        assert span.name == "agrag.vectordb.delete"
        assert span.kind is SpanKind.CLIENT
        attributes = span.attributes or {}
        assert attributes["db.system.name"] == "qdrant"
        assert attributes["db.collection.name"] == "c"
        assert span.status.status_code is StatusCode.UNSET


class TestTracingDisabled:
    """A store built without a tracer never marks a host span."""

    async def test_tracer_none_leaves_host_span_unset(self, client) -> None:
        """The host span stays UNSET with no events under tracer=None."""
        provider, exporter = _provider()
        host_tracer = provider.get_tracer("host")
        store = QdrantVectorStore(settings=QdrantSettings(), client=client, tracer=None)
        record = VectorRecord(id=uuid4(), vector=[0.1], payload={"text": "a"})
        with host_tracer.start_as_current_span("host.request"):
            await store.upsert("c", [record])
        (host_span,) = exporter.get_finished_spans()
        assert host_span.name == "host.request"
        assert host_span.status.status_code is StatusCode.UNSET
        assert list(host_span.events) == []
