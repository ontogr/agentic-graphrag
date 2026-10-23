"""Integration tests for the cached embedder wrapper.

The inner embedder is the deterministic bag-of-words fake, wrapped so that its
calls are counted. The search-level test runs two hybrid searches through a
real store to show the cache reaches the evidence tools.
"""

import asyncio
import contextlib
from collections.abc import Sequence

from agrag.common.data_models.evidence import EvidenceSearchMode
from agrag.embedding.base import Embedder
from agrag.embedding.cached import CachedEmbedder
from agrag.evidence import search_evidence
from tests.integration.retrieval.evidence._corpus import (
    BagOfWordsEmbedder,
)
from tests.integration.retrieval.evidence.conftest import EvidenceEnv


class _CountingEmbedder(Embedder):
    """Bag-of-words embedder that counts its embed and dimension calls."""

    model = "counting-bag-of-words"

    def __init__(self) -> None:
        self.embed_calls: list[list[str]] = []
        self.dimension_calls = 0

    async def dimensions(self) -> int:
        self.dimension_calls += 1
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.embed_calls.append(list(texts))
        vectors = []
        for text in texts:
            vector = [0.01] * 4
            for word in text.lower().split():
                if word in {"keep", "upload", "activity"}:
                    vector[1] += 1.0
            vectors.append(vector)
        return vectors


class TestCachedEmbedder:
    """The cache embeds each text once and returns stable vectors."""

    async def test_repeated_texts_embed_once_in_input_order(self) -> None:
        """A batch of new and cached texts embeds only the new ones, in order."""
        inner = _CountingEmbedder()
        embedder = CachedEmbedder(inner)

        first = await embedder.embed(["keep activity", "lighthouse lantern"])
        second = await embedder.embed(
            ["lighthouse lantern", "keep activity", "harbor fog"]
        )

        assert inner.embed_calls == [
            ["keep activity", "lighthouse lantern"],
            ["harbor fog"],
        ]
        assert second[1] == first[0]
        assert second[0] == first[1]
        assert second[2] is not None

    async def test_concurrent_identical_embeds_share_one_call(self) -> None:
        """Two tools embedding the same query at the same time embed it once."""
        inner = _CountingEmbedder()
        embedder = CachedEmbedder(inner)

        vectors = await asyncio.gather(
            embedder.embed(["keep activity"]),
            embedder.embed(["keep activity"]),
        )

        assert vectors[0] == vectors[1]
        assert len(inner.embed_calls) == 1

    async def test_failed_embed_is_retried_by_the_next_call(self) -> None:
        """A failed call removes its futures so the next call tries again."""

        class _FlakyEmbedder(_CountingEmbedder):
            def __init__(self) -> None:
                super().__init__()
                self.calls = 0

            async def embed(self, texts: Sequence[str]) -> list[list[float]]:
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("embedding endpoint refused at 10.0.0.4")
                return await super().embed(texts)

        inner = _FlakyEmbedder()
        embedder = CachedEmbedder(inner)

        with contextlib.suppress(RuntimeError):
            await embedder.embed(["keep activity"])
        vectors = await embedder.embed(["keep activity"])

        assert inner.calls == 2
        assert vectors[0][1] == 2.01

    async def test_cache_stores_copies_not_live_vectors(self) -> None:
        """Mutating a returned vector does not corrupt the cached value."""
        inner = _CountingEmbedder()
        embedder = CachedEmbedder(inner)

        first = await embedder.embed(["keep activity"])
        first[0][1] = 99.0
        second = await embedder.embed(["keep activity"])

        assert second[0][1] == 2.01

    async def test_lru_evicts_the_oldest_entry(self) -> None:
        """A full cache forgets its oldest text and embeds it again."""
        inner = _CountingEmbedder()
        embedder = CachedEmbedder(inner, maxsize=2)

        await embedder.embed(["a", "b"])
        await embedder.embed(["c"])
        await embedder.embed(["a"])

        assert inner.embed_calls == [["a", "b"], ["c"], ["a"]]

    async def test_dimensions_is_cached(self) -> None:
        """Only the first dimensions call reaches the inner embedder."""
        inner = _CountingEmbedder()
        embedder = CachedEmbedder(inner)

        first = await embedder.dimensions()
        second = await embedder.dimensions()

        assert first == second == 4
        assert inner.dimension_calls == 1

    async def test_distance_delegates_to_the_wrapped_embedder(self) -> None:
        """The distance of the wrapper is the distance of the inner embedder."""
        embedder = CachedEmbedder(BagOfWordsEmbedder())

        assert embedder.distance == BagOfWordsEmbedder().distance


class TestCachedEmbedderInSearch:
    """Two hybrid searches with one query embed the query once."""

    async def test_two_searches_with_one_query_embed_once(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """The second search reuses the cached query vector."""
        inner = _CountingEmbedder()
        embedder = CachedEmbedder(inner)
        scope = frozenset({evidence_env.keep, evidence_env.viber, evidence_env.harbor})

        first = await search_evidence(
            evidence_env.store,
            embedder,
            "keep upload activity database",
            mode=EvidenceSearchMode.HYBRID,
            limit=3,
            scope=scope,
        )
        second = await search_evidence(
            evidence_env.store,
            embedder,
            "keep upload activity database",
            mode=EvidenceSearchMode.HYBRID,
            limit=3,
            scope=scope,
        )

        assert first.status.value == "ok"
        assert second.status.value == "ok"
        assert list(inner.embed_calls) == [["keep upload activity database"]]
