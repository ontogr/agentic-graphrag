"""Sparse lexical vectors and the sparse embedder protocol."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from pydantic import BaseModel


class SparseVector(BaseModel):
    """A sparse vector: nonzero indices and their values.

    Attributes:
        indices: The positions of nonzero entries.
        values: The weight at each index, aligned with ``indices``.
    """

    indices: list[int]
    values: list[float]


class SparseEmbedder(ABC):
    """A component that turns text into sparse lexical vectors, for hybrid search."""

    model: str

    @abstractmethod
    async def embed(self, texts: Sequence[str]) -> list[SparseVector]:
        """Embed a batch of texts into sparse vectors.

        Args:
            texts: The texts to embed, in order.

        Returns:
            One sparse vector per input text, in the same order.
        """
