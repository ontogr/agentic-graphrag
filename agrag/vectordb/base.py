"""The asynchronous contract for an exclusive external vector index."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from types import TracebackType
from typing import ClassVar, Self
from uuid import UUID

from agrag.common.data_models.vector_record import (
    CollectionInfo,
    Distance,
    VectorHit,
    VectorKind,
    VectorRecord,
)


class VectorStore(ABC):
    """An external index whose hits must be joined to visible graph nodes.

    Writes are idempotent and immediately visible on the same client. Reads and
    deletes of missing collections return empty results. Dense scores use
    ``(1 + cosine) / 2`` or ``1 / (1 + squared_distance)``. Hybrid scores are
    rank-only, with alpha one selecting dense order and zero lexical order.
    Lexical-only search omits records that do not match the query text.
    Labels filter by any overlap. Search limits above max_results are rejected.
    """

    name: ClassVar[str]
    collection_prefix: str
    max_results: int

    @abstractmethod
    async def initialize(self) -> None:
        """Connect and authenticate, raising VectorStoreError on failure."""

    @abstractmethod
    async def close(self) -> None:
        """Release the client's connections."""

    @abstractmethod
    async def ensure_collection(
        self, kind: VectorKind, *, dimensions: int, distance: Distance
    ) -> None:
        """Create a collection or reject dimension or distance mismatches.

        DOT distance is unsupported and raises ValueError.
        """

    @abstractmethod
    async def collection_info(
        self, kind: VectorKind, *, exact_count: bool = True
    ) -> CollectionInfo | None:
        """Return collection metadata, or None if it does not exist.

        Callers that need only dimensions or existence pass ``exact_count=False``
        so the store can skip a full count and report its cheaper estimate.
        """

    @abstractmethod
    async def delete_collection(self, kind: VectorKind) -> None:
        """Delete the collection, doing nothing when it does not exist."""

    @abstractmethod
    async def upsert(
        self,
        kind: VectorKind,
        records: Sequence[VectorRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Overwrite records by id; raise VectorStoreError if collection is absent."""

    @abstractmethod
    async def search(
        self,
        kind: VectorKind,
        vector: Sequence[float],
        *,
        limit: int,
        labels: Sequence[str] | None = None,
    ) -> list[VectorHit]:
        """Return at most limit dense hits, best first, with graph-native scores."""

    @abstractmethod
    async def hybrid_search(
        self,
        kind: VectorKind,
        vector: Sequence[float],
        text: str,
        *,
        limit: int,
        alpha: float,
        labels: Sequence[str] | None = None,
    ) -> list[VectorHit]:
        """Return dense and lexical hits fused by alpha, in descending rank."""

    @abstractmethod
    async def delete(self, kind: VectorKind, ids: Sequence[UUID]) -> None:
        """Delete ids, ignoring ids and collections that do not exist."""

    @abstractmethod
    async def list_ids(
        self, kind: VectorKind, *, after: UUID | None = None, limit: int = 1000
    ) -> list[UUID]:
        """Return ids in ascending order, strictly after the exclusive cursor.

        A limit of zero returns no ids and a negative limit raises ValueError.
        Limits above max_results are allowed.
        """

    def collection_name(self, kind: VectorKind) -> str:
        """Return the prefixed collection name for a kind."""
        return f"{self.collection_prefix}_{kind.value}"

    async def __aenter__(self) -> Self:
        """Connect and return this store."""
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the store even when its context raises."""
        await self.close()
