"""Tests for the sparse embedder protocol and SparseVector model."""

from collections.abc import Sequence

import pytest

from agrag.embedding.sparse_base import SparseEmbedder, SparseVector


class _StubSparseEmbedder(SparseEmbedder):
    """A minimal sparse embedder for protocol tests."""

    model = "stub"

    async def embed(self, texts: Sequence[str]) -> list[SparseVector]:
        """Return one sparse vector per text."""
        return [SparseVector(indices=[0], values=[1.0]) for _ in texts]


class TestSparseVector:
    """SparseVector is a plain data model."""

    def test_round_trips(self) -> None:
        """The model keeps its indices and values."""
        vector = SparseVector(indices=[1, 3], values=[0.5, 0.25])
        assert vector.indices == [1, 3]
        assert vector.values == [0.5, 0.25]


class TestSparseEmbedder:
    """SparseEmbedder is an abstract protocol with one method."""

    def test_cannot_instantiate(self) -> None:
        """The base class cannot be constructed directly."""
        with pytest.raises(TypeError):
            SparseEmbedder()  # type: ignore[abstract]

    async def test_stub_embed_returns_one_vector_per_text(self) -> None:
        """A concrete embedder returns one sparse vector per input text."""
        embedder = _StubSparseEmbedder()
        texts = ["alpha", "beta"]
        vectors = await embedder.embed(texts)
        assert len(vectors) == 2
        assert all(isinstance(v, SparseVector) for v in vectors)

    def test_model_attribute(self) -> None:
        """The model name is exposed as an attribute."""
        embedder = _StubSparseEmbedder()
        assert embedder.model == "stub"
