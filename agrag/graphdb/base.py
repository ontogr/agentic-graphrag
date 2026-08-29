"""The GraphStore abstraction and its build shortcut helpers."""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from typing import Any

from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.vector_record import Distance, VectorHit


class GraphStore(ABC):
    """A graph database backend: schema, writes, and native vector search."""

    @abstractmethod
    async def connect(self) -> None:
        """Open the backend connection and verify connectivity."""

    @abstractmethod
    async def close(self) -> None:
        """Release the backend connection."""

    @abstractmethod
    def session(self) -> AbstractAsyncContextManager[Any]:
        """Open a session as an async context manager.

        Returns:
            A context manager yielding a backend session.
        """

    @abstractmethod
    async def execute_read(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a read transaction.

        Args:
            query: The Cypher query to run.
            parameters: The query parameters.

        Returns:
            The result rows as dicts.
        """

    @abstractmethod
    async def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a write transaction.

        Args:
            query: The Cypher query to run.
            parameters: The query parameters.

        Returns:
            The result rows as dicts.
        """

    @abstractmethod
    async def setup_constraints(self) -> None:
        """Create per-label uniqueness constraints for tracked labels."""

    @abstractmethod
    async def setup_indexes(self) -> None:
        """Create per-label property indexes for tracked labels."""

    @abstractmethod
    async def upsert_nodes(
        self,
        label: str,
        nodes: Sequence[NodeRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Write or merge nodes of one label.

        Args:
            label: The node label.
            nodes: The node records to upsert.
            batch_size: Records per backend write call.
        """

    @abstractmethod
    async def upsert_relations(
        self,
        relations: Sequence[RelationRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Write or merge relationships between existing nodes.

        Args:
            relations: The relation records to upsert.
            batch_size: Records per backend write call.
        """

    @abstractmethod
    async def ensure_vector_index(
        self, *, label: str, vector_property: str, dimensions: int, distance: Distance
    ) -> None:
        """Create a native vector index if it does not exist.

        Args:
            label: The node label to index.
            vector_property: The embedding property name.
            dimensions: The embedding dimension.
            distance: The distance metric.
        """

    @abstractmethod
    async def vector_search(
        self,
        *,
        label: str,
        vector_property: str,
        query_vector: Sequence[float],
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        """Search nodes by dense vector.

        Args:
            label: The node label to search.
            vector_property: The embedding property name.
            query_vector: The dense query embedding.
            limit: Maximum number of hits.
            filters: An optional flat-dict filter on node properties.

        Returns:
            The matched hits, highest score first.
        """

    async def __aenter__(self) -> "GraphStore":
        """Open the store and verify connectivity.

        Returns:
            The connected store.
        """
        await self.connect()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Close the store, releasing the connection."""
        await self.close()
