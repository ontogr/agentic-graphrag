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
        """Embed a batch of documents into sparse vectors.

        Args:
            texts: The document texts to embed, in order.

        Returns:
            One sparse vector per input text, in the same order.
        """

    @abstractmethod
    async def query_embed(self, texts: Sequence[str]) -> list[SparseVector]:
        """Embed a batch of search queries into sparse vectors.

        Query-side sparse embedding is not always the same computation as
        document-side embedding: BM25, for example, applies term-frequency
        and document-length normalization on the document side but only a
        uniform per-term weight on the query side, since IDF weighting is
        applied by the sparse index at query time instead. Implementations
        with no such asymmetry may implement this identically to ``embed``.

        Args:
            texts: The query texts to embed, in order.

        Returns:
            One sparse vector per input text, in the same order.
        """
