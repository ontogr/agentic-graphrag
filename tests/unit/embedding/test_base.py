"""Tests for the Embedder protocol, cache seam, and base behavior."""

from collections.abc import Sequence

from agrag.embedding.base import (
    Embedder,
    EmbeddingCache,
    NullEmbeddingCache,
)


class _RecordingCache(EmbeddingCache):
    """A cache that records every get and set for assertions."""

    def __init__(self) -> None:
        """Create an empty cache."""
        self.store: dict[tuple[str, str], list[float]] = {}
        self.get_calls = 0

    async def get(self, *, text: str, model: str) -> list[float] | None:
        """Return the stored vector, or None on a miss."""
        self.get_calls += 1
        return self.store.get((text, model))

    async def set(self, *, text: str, model: str, vector: list[float]) -> None:
        """Store the vector."""
        self.store[(text, model)] = vector


class _StubEmbedder(Embedder):
    """A minimal Embedder whose embed returns fixed per-text vectors."""

    model = "stub-model"
    dimensions = 2

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one fixed vector per input text."""
        self.calls.append(list(texts))
        return [[float(i), 0.0] for i in range(len(texts))]


class TestNullEmbeddingCache:
    """The null cache never stores and always misses."""

    async def test_get_always_misses(self) -> None:
        """Get returns None."""
        assert await NullEmbeddingCache().get(text="a", model="m") is None

    async def test_set_is_noop(self) -> None:
        """Set does nothing and does not raise."""
        await NullEmbeddingCache().set(text="a", model="m", vector=[1.0])


class TestEmbeddingCacheContract:
    """A real cache stores and returns vectors by (text, model)."""

    async def test_set_then_get(self) -> None:
        """Set populates a key that get returns."""
        cache = _RecordingCache()
        assert await cache.get(text="a", model="m") is None
        await cache.set(text="a", model="m", vector=[0.1, 0.2])
        assert await cache.get(text="a", model="m") == [0.1, 0.2]

    async def test_keys_are_distinct(self) -> None:
        """The same text under different models is a different key."""
        cache = _RecordingCache()
        await cache.set(text="a", model="m1", vector=[1.0])
        assert await cache.get(text="a", model="m2") is None


class TestEmbedderEmbedOne:
    """embed_one delegates to embed with a single-item batch."""

    async def test_embed_one_returns_first_vector(self) -> None:
        """embed_one returns the single vector and calls embed once."""
        embedder = _StubEmbedder()
        vector = await embedder.embed_one("hello")
        assert vector == [0.0, 0.0]
        assert embedder.calls == [["hello"]]
