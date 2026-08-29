"""Tests for the FastEmbed BM25 sparse embedder."""

import sys
from unittest import mock

import pytest

from agrag.embedding.errors import EmbeddingMissingExtraError
from agrag.embedding.fastembed_bm25 import DEFAULT_BM25_MODEL, FastEmbedBM25Embedder
from agrag.embedding.sparse_base import SparseVector


class FakeSparseModel:
    """A stand-in for a FastEmbed sparse model in tests."""

    model_name = DEFAULT_BM25_MODEL

    def embed(self, texts: list[str]):
        """Return one sparse vector per text, with int indices and float values."""
        return [
            type("SV", (), {"indices": [i], "values": [1.0]})()
            for i, _ in enumerate(texts)
        ]


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
        embedder = FastEmbedBM25Embedder(model=FakeSparseModel.model_name)
        assert embedder._model is None


class TestFastEmbedBM25Embed:
    """Embed delegates to FastEmbed in a worker thread."""

    async def test_embed_returns_sparse_vectors(self) -> None:
        """Embed returns one SparseVector per text in order."""
        embedder = FastEmbedBM25Embedder(model=FakeSparseModel.model_name)
        embedder._model = FakeSparseModel()
        vectors = await embedder.embed(["a", "b"])
        assert len(vectors) == 2
        assert all(isinstance(v, SparseVector) for v in vectors)
        assert vectors[0].indices == [0]
        assert vectors[0].values == [1.0]


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
