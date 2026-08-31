"""Tests for the FastEmbed BM25 sparse embedder."""

import asyncio
import sys
import threading
from unittest import mock

import pytest

from agrag.embedding.errors import EmbeddingMissingExtraError
from agrag.embedding.fastembed_bm25 import DEFAULT_BM25_MODEL, FastEmbedBM25Embedder
from agrag.embedding.sparse_base import SparseVector


class MockSparseModel:
    """A stand-in for a FastEmbed sparse model in tests."""

    model_name = DEFAULT_BM25_MODEL

    def embed(self, texts: list[str]):
        """Return one document sparse vector per text, weighted by index."""
        return [
            type("SV", (), {"indices": [i], "values": [1.0]})()
            for i, _ in enumerate(texts)
        ]

    def query_embed(self, texts: list[str]):
        """Return one query sparse vector per text, at a fixed index and weight.

        Distinct output from ``embed`` so tests can prove ``query_embed``
        delegates to this method, not the document-side ``embed``.
        """
        return [type("SV", (), {"indices": [9], "values": [1.0]})() for _ in texts]


class TestFastEmbedBM25Construction:
    """Construction resolves the model name."""

    def test_default_model_name(self) -> None:
        """The default model name is the FastEmbed BM25 default."""
        embedder = FastEmbedBM25Embedder()
        assert embedder.model == DEFAULT_BM25_MODEL

    def test_explicit_model_name(self) -> None:
        """An explicit model name is exposed."""
        embedder = FastEmbedBM25Embedder(model="custom/bm25")
        assert embedder.model == "custom/bm25"

    def test_model_not_loaded_on_construct(self) -> None:
        """Construction does not import or build the model."""
        embedder = FastEmbedBM25Embedder(model=MockSparseModel.model_name)
        assert embedder._model is None


class TestFastEmbedBM25Embed:
    """Embed delegates to FastEmbed in a worker thread."""

    async def test_embed_returns_sparse_vectors(self) -> None:
        """Embed returns one SparseVector per text in order."""
        embedder = FastEmbedBM25Embedder(model=MockSparseModel.model_name)
        embedder._model = MockSparseModel()
        vectors = await embedder.embed(["a", "b"])
        assert len(vectors) == 2
        assert all(isinstance(v, SparseVector) for v in vectors)
        assert vectors[0].indices == [0]
        assert vectors[0].values == [1.0]

    async def test_query_embed_uses_query_side_weighting(self) -> None:
        """query_embed delegates to the model's query_embed, not its embed.

        Regression guard: BM25's document embedding applies term-frequency
        and length-normalization weighting meant for passages. Sending
        query text through that path instead of the model's query-side
        method would rank matches incorrectly.
        """
        embedder = FastEmbedBM25Embedder(model=MockSparseModel.model_name)
        model = MockSparseModel()
        embedder._model = model
        vectors = await embedder.query_embed(["a", "b"])
        assert len(vectors) == 2
        assert all(v.indices == [9] for v in vectors)


class TestFastEmbedBM25ConcurrentLoad:
    """Concurrent first-time embeds must share one model build, not race it."""

    async def test_concurrent_embeds_build_model_once(self) -> None:
        """A second concurrent embed waits for, and reuses, the first build.

        Regression guard: without locking, both calls would see ``self._model
        is None`` before either finishes building, and each would construct
        its own model.
        """
        build_calls = 0
        entered = threading.Event()
        release = threading.Event()

        def slow_build(_self: FastEmbedBM25Embedder) -> MockSparseModel:
            nonlocal build_calls
            build_calls += 1
            entered.set()
            release.wait(timeout=5)
            return MockSparseModel()

        embedder = FastEmbedBM25Embedder()
        with mock.patch.object(
            FastEmbedBM25Embedder,
            "_build_model",
            autospec=True,
            side_effect=slow_build,
        ):
            first = asyncio.create_task(embedder.embed(["a"]))
            await asyncio.to_thread(entered.wait, 5)
            second = asyncio.create_task(embedder.embed(["b"]))
            await asyncio.sleep(0.05)
            release.set()
            await asyncio.gather(first, second)

        assert build_calls == 1


class TestFastEmbedBM25MissingExtra:
    """Without the extra installed, use raises, not ImportError."""

    async def test_embed_raises_missing_extra(self) -> None:
        """Embedding without fastembed raises EmbeddingMissingExtraError."""
        embedder = FastEmbedBM25Embedder()
        with (
            mock.patch.dict(sys.modules, {"fastembed": None}),
            pytest.raises(EmbeddingMissingExtraError) as exc_info,
        ):
            await embedder.embed(["x"])
        assert exc_info.value.extra == "qdrant"
