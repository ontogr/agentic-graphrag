"""Embedder wrapper that caches query vectors in memory."""

import asyncio
from collections import OrderedDict
from collections.abc import Sequence

from agrag.common.data_models.vector_record import Distance
from agrag.embedding.base import Embedder


class CachedEmbedder(Embedder):
    """An ``Embedder`` that caches query vectors and deduplicates in-flight calls.

    Wraps another embedder with an in-memory LRU keyed by text, so repeated
    queries (for example the same query hitting two search tools in one
    turn) embed once. Texts that are cached or already being embedded by an
    earlier call are not sent to the inner embedder; the remaining texts go
    in one batch call. A failed inner call resolves its in-flight futures
    with the error and is retried on the next call. Cached vectors are
    stored and returned as copies, so callers cannot mutate them.
    """

    def __init__(self, inner: Embedder, *, maxsize: int = 256) -> None:
        """Build the cached embedder.

        Args:
            inner: The embedder that performs the actual embedding.
            maxsize: The most vectors the LRU cache holds. The least
                recently used entry is evicted beyond this.
        """
        self._inner = inner
        self._maxsize = maxsize
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._in_flight: dict[str, asyncio.Future[list[float]]] = {}
        self._dimensions: int | None = None

    @property
    def model(self) -> str:
        """The wrapped embedder's model name."""
        return self._inner.model

    @property
    def distance(self) -> Distance:
        """The wrapped embedder's distance metric."""
        return self._inner.distance

    async def dimensions(self) -> int:
        """Return the wrapped embedder's dimension, cached after the first call.

        Returns:
            The dimension of the vectors the wrapped embedder produces.
        """
        if self._dimensions is None:
            self._dimensions = await self._inner.dimensions()
        return self._dimensions

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a batch of texts, using the cache and in-flight sharing.

        Args:
            texts: The texts to embed, in order. Duplicates are embedded
                once.

        Returns:
            One vector per input text, in the same order. Vector values are
            fresh copies; mutating a returned vector never changes the
            cache.
        """
        unique_texts = list(dict.fromkeys(texts))
        futures: dict[str, asyncio.Future[list[float]]] = {}
        started: list[str] = []
        for text in unique_texts:
            if self._cache_get(text) is not None:
                continue
            future = self._in_flight.get(text)
            if future is None:
                future = asyncio.get_running_loop().create_future()
                self._in_flight[text] = future
                started.append(text)
            futures[text] = future

        if started:
            try:
                vectors = await self._inner.embed(started)
                for text, vector in zip(started, vectors, strict=True):
                    self._cache_put(text, list(vector))
                    future = self._in_flight.pop(text, None)
                    if future is not None and not future.done():
                        future.set_result(list(vector))
            except BaseException as exc:
                for text in started:
                    future = self._in_flight.pop(text, None)
                    if future is not None and not future.done():
                        future.set_exception(exc)
                        # The initiating caller raises directly instead of
                        # awaiting its future; read the exception once so
                        # asyncio does not log it as never retrieved.
                        future.exception()
                raise

        results: list[list[float]] = []
        for text in texts:
            cached = self._cache_get(text)
            if cached is not None:
                results.append(list(cached))
                continue
            results.append(list(await futures[text]))
        return results

    def _cache_get(self, text: str) -> list[float] | None:
        """Return the cached vector for ``text``, refreshing its recency."""
        vector = self._cache.get(text)
        if vector is not None:
            self._cache.move_to_end(text)
        return vector

    def _cache_put(self, text: str, vector: list[float]) -> None:
        """Store ``vector`` in the LRU cache, evicting the oldest entry."""
        self._cache[text] = vector
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)
