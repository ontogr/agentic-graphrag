"""The Embedder and EmbeddingCache protocols."""

from abc import ABC, abstractmethod
from collections.abc import Sequence


class EmbeddingCache(ABC):
    """A content-addressed cache for embedding vectors.

    ``normalize`` is part of the cache key alongside ``text`` and ``model``
    because it changes the vector an embedder produces for the same text and
    model: without it, embedders sharing one cache but configured with
    opposite ``EmbeddingSettings.normalize`` values would read back the wrong
    output mode. Any future embedder setting that changes output values must
    join this key the same way.
    """

    @abstractmethod
    async def get(
        self, *, text: str, model: str, normalize: bool
    ) -> list[float] | None:
        """Return the cached vector for ``(text, model, normalize)``.

        Returns:
            The cached vector, or ``None`` on a miss.
        """

    @abstractmethod
    async def set(
        self, *, text: str, model: str, normalize: bool, vector: list[float]
    ) -> None:
        """Store ``vector`` under ``(text, model, normalize)``."""


class NullEmbeddingCache(EmbeddingCache):
    """A cache that never stores anything. The default when none is injected."""

    async def get(
        self, *, text: str, model: str, normalize: bool
    ) -> list[float] | None:
        """Always miss."""
        return None

    async def set(
        self, *, text: str, model: str, normalize: bool, vector: list[float]
    ) -> None:
        """Do nothing."""


class Embedder(ABC):
    """A component that turns text into dense embedding vectors."""

    model: str

    @abstractmethod
    async def dimensions(self) -> int:
        """Return the dimension of the vectors this embedder produces.

        Async because a lazily-loaded embedder may need to load its model to
        answer, and that load must go through the same worker-thread/lock
        path ``embed`` uses rather than blocking the event loop.
        """

    @abstractmethod
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a batch of texts.

        Args:
            texts: The texts to embed, in order.

        Returns:
            One vector per input text, in the same order.
        """

    async def embed_one(self, text: str) -> list[float]:
        """Embed a single text.

        Args:
            text: The text to embed.

        Returns:
            The text's embedding vector.
        """
        return (await self.embed([text]))[0]
