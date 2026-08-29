"""The Embedder and EmbeddingCache protocols."""

from abc import ABC, abstractmethod
from collections.abc import Sequence


class EmbeddingCache(ABC):
    """A content-addressed cache for embedding vectors."""

    @abstractmethod
    async def get(self, *, text: str, model: str) -> list[float] | None:
        """Return the cached vector for ``(text, model)``, or ``None`` on a miss."""

    @abstractmethod
    async def set(self, *, text: str, model: str, vector: list[float]) -> None:
        """Store ``vector`` under ``(text, model)``."""


class NullEmbeddingCache(EmbeddingCache):
    """A cache that never stores anything. The default when none is injected."""

    async def get(self, *, text: str, model: str) -> list[float] | None:
        """Always miss."""
        return None

    async def set(self, *, text: str, model: str, vector: list[float]) -> None:
        """Do nothing."""


class Embedder(ABC):
    """A component that turns text into dense embedding vectors."""

    model: str
    dimensions: int

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
