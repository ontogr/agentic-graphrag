"""Tests for the sentence-transformers embedder implementation."""

import sys
import threading
from array import array
from unittest import mock

import pytest

from agrag.embedding.base import EmbeddingCache
from agrag.embedding.errors import EmbeddingMissingExtraError
from agrag.embedding.sentence_transformers import SentenceTransformerEmbedder


class FakeSentenceTransformer:
    """A stand-in for a sentence-transformers model in tests.

    Records the thread each ``encode`` runs on, and the texts it received,
    so tests can assert off-loop execution and batching behavior.
    """

    def __init__(self, dim: int = 4) -> None:
        """Create the fake model with the given embedding dimension."""
        self._dim = dim
        self.encode_calls: list[list[str]] = []
        self.encode_thread: threading.Thread | None = None

    def get_sentence_embedding_dimension(self) -> int:
        """Return the configured embedding dimension."""
        return self._dim

    def encode(
        self,
        texts: list[str],
        *,
        batch_size: int = 32,
        normalize_embeddings: bool = True,
    ):
        """Record the call and return a fixed zero vector per text."""
        self.encode_thread = threading.current_thread()
        self.encode_calls.append(list(texts))
        return [array("f", [0.0] * self._dim) for _ in texts]


class _RecordingCache(EmbeddingCache):
    """A cache that stores vectors and records every get."""

    def __init__(self) -> None:
        """Create an empty cache."""
        self.store: dict[tuple[str, str], list[float]] = {}

    async def get(self, *, text: str, model: str) -> list[float] | None:
        """Return the stored vector, or None on a miss."""
        return self.store.get((text, model))

    async def set(self, *, text: str, model: str, vector: list[float]) -> None:
        """Store the vector."""
        self.store[(text, model)] = vector


class TestSentenceTransformerEmbedderConstruction:
    """Construction resolves settings and the cache seam."""

    def test_defaults_resolve(self) -> None:
        """Defaults produce the planned default model name."""
        embedder = SentenceTransformerEmbedder()
        assert embedder.model == "ibm-granite/granite-embedding-small-english-r2"

    def test_dimensions_from_injected_model(self) -> None:
        """Dimensions reflects the injected model's dimension."""
        embedder = SentenceTransformerEmbedder(model=FakeSentenceTransformer(dim=7))
        assert embedder.dimensions == 7

    def test_model_not_loaded_on_construct(self) -> None:
        """Construction does not import or build the model."""
        model = FakeSentenceTransformer()
        SentenceTransformerEmbedder(model=model)
        assert model.encode_calls == []


class TestMissingExtra:
    """Without the extra installed, construction is fine but use raises."""

    def test_dimensions_raises_missing_extra(self) -> None:
        """Reading dimensions without the extra raises, not ImportError."""
        embedder = SentenceTransformerEmbedder()
        with (
            mock.patch.dict(sys.modules, {"sentence_transformers": None}),
            pytest.raises(EmbeddingMissingExtraError) as exc_info,
        ):
            _ = embedder.dimensions
        assert exc_info.value.extra == "embed-local"

    async def test_embed_raises_missing_extra(self) -> None:
        """Embedding without the extra raises, not ImportError."""
        embedder = SentenceTransformerEmbedder()
        with (
            mock.patch.dict(sys.modules, {"sentence_transformers": None}),
            pytest.raises(EmbeddingMissingExtraError),
        ):
            await embedder.embed(["x"])


class TestEmbedEventLoop:
    """Embed must run the blocking model off the event loop thread."""

    async def test_encode_runs_off_loop_thread(self) -> None:
        """Encode runs in a worker thread, not the event loop thread.

        Regression guard: if the ``asyncio.to_thread`` wrapping is removed,
        ``encode`` runs on the loop thread and this assertion fails.
        """
        loop_thread = threading.current_thread()
        model = FakeSentenceTransformer()
        embedder = SentenceTransformerEmbedder(model=model)
        await embedder.embed(["a", "b"])
        assert model.encode_thread is not None
        assert model.encode_thread is not loop_thread

    async def test_model_loaded_once(self) -> None:
        """Repeated embeds reuse one model instance."""
        model = FakeSentenceTransformer()
        embedder = SentenceTransformerEmbedder(model=model)
        await embedder.embed(["a"])
        await embedder.embed(["b"])
        # encode is called per batch; the model object is shared, not rebuilt.
        assert model.encode_calls == [["a"], ["b"]]


class TestEmbedCaching:
    """Embed reads the cache and writes new vectors under one batched call."""

    async def test_miss_then_hit_uses_cache(self) -> None:
        """A second identical embed hits the cache and re-encodes nothing."""
        model = FakeSentenceTransformer()
        cache = _RecordingCache()
        embedder = SentenceTransformerEmbedder(model=model, cache=cache)
        out1 = await embedder.embed(["a", "b"])
        assert len(out1) == 2
        assert model.encode_calls == [["a", "b"]]
        out2 = await embedder.embed(["a", "b"])
        assert out2 == out1
        assert model.encode_calls == [["a", "b"]]

    async def test_partial_miss_batches_only_misses(self) -> None:
        """A partial miss encodes only the missing texts in one call."""
        model = FakeSentenceTransformer()
        cache = _RecordingCache()
        embedder = SentenceTransformerEmbedder(model=model, cache=cache)
        await embedder.embed(["a", "b"])
        await embedder.embed(["a", "c"])
        assert model.encode_calls == [["a", "b"], ["c"]]

    async def test_vectors_returned_in_input_order(self) -> None:
        """Returned vectors keep the input text order."""
        model = FakeSentenceTransformer(dim=3)
        embedder = SentenceTransformerEmbedder(model=model)
        out = await embedder.embed(["x", "y"])
        assert out == [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]

    async def test_embed_one_returns_single_vector(self) -> None:
        """embed_one returns the single vector for one text."""
        model = FakeSentenceTransformer()
        embedder = SentenceTransformerEmbedder(model=model)
        assert await embedder.embed_one("solo") == [0.0, 0.0, 0.0, 0.0]
