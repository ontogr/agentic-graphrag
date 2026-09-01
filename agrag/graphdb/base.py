"""The GraphStore abstraction and its build shortcut helpers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, Protocol

from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.vector_record import Distance, VectorHit


class GraphStoreTransaction(Protocol):
    """The read/write/upsert surface available inside a ``transaction()`` block.

    A structural type, not a base class: ``GraphStore`` itself satisfies it
    (the default ``transaction()`` yields ``self``), and a backend's own
    transaction handle, such as Neo4j's, satisfies it without inheriting from
    anything here.
    """

    async def execute_read(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a read inside the surrounding transaction."""
        ...

    async def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a write inside the surrounding transaction."""
        ...

    async def upsert_nodes(
        self,
        label: str,
        nodes: Sequence[NodeRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Write or merge nodes inside the surrounding transaction."""
        ...


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
        self,
        query: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        """Run a read transaction.

        Args:
            query: The Cypher query to run.
            parameters: The query parameters.
            timeout: Server-side transaction timeout in seconds. The
                database terminates the transaction when it runs
                longer. None uses the server's default timeout.
                Backends that cannot enforce a timeout ignore it.

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
        """Create per-label and per-relation-type uniqueness constraints.

        Constraints cover every node label and relationship type written
        through this instance or already present in the database, so a fresh
        instance can set up an existing database without first rewriting
        every record.
        """

    @abstractmethod
    async def setup_indexes(self) -> None:
        """Create per-label property indexes.

        Covers every node label written through this instance or already
        present in the database, so a fresh instance can set up an existing
        database without first rewriting every record.
        """

    @abstractmethod
    async def register_labels(self, labels: Sequence[str]) -> None:
        """Mark labels as known, without writing anything.

        setup_constraints()/setup_indexes() only cover labels this instance
        has already written (or that already exist live in the database) —
        both empty on a brand-new database. register_labels lets a caller
        holding a GraphSchema (Graph.open()) provision a fresh database
        fully before its first write.

        Args:
            labels: The labels to register. Each must be a safe Cypher
                identifier.

        Raises:
            ValueError: Any label is not a safe identifier.
        """

    @abstractmethod
    async def register_relation_types(self, types: Sequence[str]) -> None:
        """Mark relationship types as known, without writing anything.

        The relationship-type counterpart to register_labels — see its
        docstring for why this exists.

        Args:
            types: The relationship types to register. Each must be a safe
                Cypher identifier.

        Raises:
            ValueError: Any type is not a safe identifier.
        """

    @abstractmethod
    async def upsert_nodes(
        self,
        label: str,
        nodes: Sequence[NodeRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Write or merge nodes, honoring each record's full label set.

        Args:
            label: The label this batch is tracked under for constraint and
                index bookkeeping.
            nodes: The node records to upsert. Each node's ``NodeRecord.labels``
                names the full label set actually written to it, which may
                include labels beyond ``label``.
            batch_size: Records per backend write call, applied within each
                distinct label set when ``nodes`` mixes more than one. Must
                be positive.

        Raises:
            ValueError: ``batch_size`` is not positive.
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
            batch_size: Records per backend write call. Must be positive.

        Raises:
            ValueError: ``batch_size`` is not positive.
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

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[GraphStoreTransaction]:
        """Start an explicit transaction spanning multiple writes.

        Every call through the yielded handle should join one backend
        transaction, committing as a whole on clean exit from the
        ``async with`` block and rolling back as a whole if the block raises.
        The default here simply yields ``self`` and gives no atomicity beyond
        what each individual call already provides; a backend that can offer
        real atomicity, such as ``Neo4jGraphStore``, overrides this with a
        driver transaction.

        Use this when a caller must guarantee several writes either all apply
        or none do, such as ``apply_merge``'s tombstone, relationship
        transfer, and dedup steps.

        Returns:
            An async context manager yielding the transactional handle.
        """
        yield self

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
