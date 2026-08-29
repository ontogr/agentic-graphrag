"""The VectorStore abstraction and its build shortcut."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from agrag.common.data_models.vector_record import Distance, VectorHit, VectorRecord


class VectorStore(ABC):
    """A vector database backend: collection lifecycle, writes, and search."""

    @abstractmethod
    async def initialize(self) -> None:
        """Check connectivity and authentication.

        Raises:
            VectorStoreError: The backend is unreachable, or the credentials
                are rejected.
        """

    @abstractmethod
    async def ensure_collection(
        self, name: str, *, dimensions: int, distance: Distance, hybrid: bool = False
    ) -> None:
        """Create the collection if it does not exist.

        Args:
            name: The collection name.
            dimensions: The embedding dimension. If the collection already
                exists with a different dimension, this raises.
            distance: The distance metric new collections use.
            hybrid: Whether to additionally provision the sparse-vector
                configuration hybrid search needs. Ignored by backends that
                need no such provisioning.

        Raises:
            CollectionDimensionMismatchError: The collection exists with a
                different dimension than ``dimensions``.
        """

    @abstractmethod
    async def collection_exists(self, name: str) -> bool:
        """Report whether a collection exists.

        Args:
            name: The collection name.

        Returns:
            ``True`` if the collection exists.
        """

    @abstractmethod
    async def delete_collection(self, name: str) -> None:
        """Delete a collection and all its points.

        Args:
            name: The collection name.
        """

    @abstractmethod
    async def upsert(
        self,
        collection: str,
        records: Sequence[VectorRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Write or overwrite records in a collection.

        Args:
            collection: The collection to write to.
            records: The records to upsert, in order.
            batch_size: The number of records per backend write call.
        """

    @abstractmethod
    async def search(
        self,
        collection: str,
        query_vector: Sequence[float],
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        """Search by dense vector only.

        Args:
            collection: The collection to search.
            query_vector: The dense query embedding.
            limit: The maximum number of hits to return.
            filters: A flat-dict filter: a scalar value means exact match, a
                list value means any of, and all keys are AND-ed together.

        Returns:
            The matched hits, highest score first.
        """

    @abstractmethod
    async def hybrid_search(
        self,
        collection: str,
        query_vector: Sequence[float],
        query_text: str,
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        alpha: float = 0.5,
    ) -> list[VectorHit]:
        """Search by dense vector and keyword text in one fused call.

        Args:
            collection: The collection to search. Must have been created with
                ``ensure_collection(..., hybrid=True)``.
            query_vector: The dense query embedding.
            query_text: The query text, matched by keyword/BM25.
            limit: The maximum number of hits to return.
            filters: A flat-dict filter: a scalar value means exact match, a
                list value means any of, and all keys are AND-ed together.
            alpha: The dense/keyword balance. ``1.0`` is pure dense, ``0.0`` is
                pure keyword. Weaviate and Milvus apply this weight natively.
                Qdrant's native fusion (Reciprocal Rank Fusion) has no
                continuous weight, so it applies ``alpha`` by blending two
                independently-scored, min-max normalized result sets instead
                of a single native fused call.

        Returns:
            The fused hits, highest score first.
        """

    @abstractmethod
    async def scroll(
        self,
        collection: str,
        *,
        limit: int = 100,
        page_offset: str | None = None,
        filters: dict[str, Any] | None = None,
        with_vectors: bool = False,
    ) -> tuple[list[VectorRecord], str | None]:
        """Iterate records in a collection, in batches.

        Args:
            collection: The collection to read.
            limit: The maximum number of records per page.
            page_offset: The offset from a previous ``scroll`` call, or
                ``None`` to start at the beginning.
            filters: A flat-dict filter: a scalar value means exact match, a
                list value means any of, and all keys are AND-ed together.
            with_vectors: Whether to return each record's vector.

        Returns:
            The page of records and the next page offset, or ``None`` at the
            end.
        """

    @abstractmethod
    async def retrieve(
        self, collection: str, ids: Sequence[UUID]
    ) -> list[VectorRecord]:
        """Fetch records by id.

        Args:
            collection: The collection to read.
            ids: The ids to fetch.

        Returns:
            The records that exist, in the requested order, omitting missing
            ids.
        """

    @abstractmethod
    async def count(
        self, collection: str, *, filters: dict[str, Any] | None = None
    ) -> int:
        """Count records in a collection.

        Args:
            collection: The collection to count.
            filters: A flat-dict filter: a scalar value means exact match, a
                list value means any of, and all keys are AND-ed together.

        Returns:
            The number of matching records.
        """

    @abstractmethod
    async def delete(self, collection: str, ids: Sequence[UUID]) -> None:
        """Delete records by id.

        Args:
            collection: The collection to delete from.
            ids: The ids to delete.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release the backend connection."""

    async def __aenter__(self) -> "VectorStore":
        """Open the store and check connectivity.

        Returns:
            The connected store.
        """
        await self.initialize()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Close the store, releasing the connection."""
        await self.close()
