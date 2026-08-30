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
        self.store: dict[tuple[str, str, bool], list[float]] = {}
        self.get_calls = 0

    async def get(
        self, *, text: str, model: str, normalize: bool
    ) -> list[float] | None:
        """Return the stored vector, or None on a miss."""
        self.get_calls += 1
        return self.store.get((text, model, normalize))

    async def set(
        self, *, text: str, model: str, normalize: bool, vector: list[float]
    ) -> None:
        """Store the vector."""
        self.store[(text, model, normalize)] = vector


class _StubEmbedder(Embedder):
    """A minimal Embedder whose embed returns fixed per-text vectors."""

    model = "stub-model"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def dimensions(self) -> int:
        """Return the fixed stub dimension."""
        return 2

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one fixed vector per input text."""
        self.calls.append(list(texts))
        return [[float(i), 0.0] for i in range(len(texts))]


class TestNullEmbeddingCache:
    """The null cache never stores and always misses."""

    async def test_get_always_misses(self) -> None:
        """Get returns None."""
        cache = NullEmbeddingCache()
        assert await cache.get(text="a", model="m", normalize=True) is None

    async def test_set_is_noop(self) -> None:
        """Set does nothing and does not raise."""
        cache = NullEmbeddingCache()
        await cache.set(text="a", model="m", normalize=True, vector=[1.0])


class TestEmbeddingCacheContract:
    """A real cache stores and returns vectors by (text, model, normalize)."""

    async def test_set_then_get(self) -> None:
        """Set populates a key that get returns."""
        cache = _RecordingCache()
        assert await cache.get(text="a", model="m", normalize=True) is None
        await cache.set(text="a", model="m", normalize=True, vector=[0.1, 0.2])
        assert await cache.get(text="a", model="m", normalize=True) == [0.1, 0.2]

    async def test_keys_are_distinct_by_model(self) -> None:
        """The same text under different models is a different key."""
        cache = _RecordingCache()
        await cache.set(text="a", model="m1", normalize=True, vector=[1.0])
        assert await cache.get(text="a", model="m2", normalize=True) is None

    async def test_keys_are_distinct_by_normalize(self) -> None:
        """The same text and model under different normalize is a different key."""
        cache = _RecordingCache()
        await cache.set(text="a", model="m", normalize=True, vector=[1.0])
        assert await cache.get(text="a", model="m", normalize=False) is None


class TestEmbedderEmbedOne:
    """embed_one delegates to embed with a single-item batch."""

    async def test_embed_one_returns_first_vector(self) -> None:
        """embed_one returns the single vector and calls embed once."""
        embedder = _StubEmbedder()
        vector = await embedder.embed_one("hello")
        assert vector == [0.0, 0.0]
        assert embedder.calls == [["hello"]]
