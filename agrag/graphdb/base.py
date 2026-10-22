"""The GraphStore abstraction and its build shortcut helpers."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol, TypeVar
from uuid import UUID

from agrag.common.data_models.candidate import CandidateRecord
from agrag.common.data_models.graph_record import (
    DeferredWrites,
    NodeRecord,
    RelationRecord,
    UpsertResult,
)
from agrag.common.data_models.index_record import IndexInfo, SearchCall
from agrag.common.data_models.vector_record import Distance, VectorHit
from agrag.cypher.relations import shortest_path_distance_query


_T = TypeVar("_T")


class GraphStoreTransaction(Protocol):
    """The read/write/upsert surface available inside transactional work.

    A structural type, not a base class: ``GraphStore`` itself satisfies it
    (the default ``run_in_transaction()`` passes ``self``), and a backend's own
    transaction handle, such as Neo4j's, satisfies it without inheriting from
    anything here.
    """

    def vector_value(self, expression: str) -> str:
        """Wrap a Cypher expression that holds an embedding for a property write.

        Returns:
            The expression to assign to a vector property. Backends that store
            a plain float list return ``expression`` unchanged.
        """
        return expression

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
        pending_job_id: UUID | None = None,
        deferred: DeferredWrites | None = None,
    ) -> UpsertResult | None:
        """Write or merge nodes inside the surrounding transaction.

        ``pending_job_id`` tags the rows the call creates. A write that reaches
        a row the job did not create is not applied and is added to ``deferred``,
        which is required when ``pending_job_id`` is set.

        Raises:
            GraphStoreWriteConflictError: ``deferred`` is None and a row is
                owned by another in-flight job. The transaction rolls back.
        """
        ...

    async def upsert_relations(
        self,
        relations: Sequence[RelationRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
        deferred: DeferredWrites | None = None,
    ) -> UpsertResult | None:
        """Write or merge relationships inside the surrounding transaction.

        ``pending_job_id`` tags the rows the call creates. A write that reaches
        a row the job did not create is not applied and is added to ``deferred``,
        which is required when ``pending_job_id`` is set.

        Raises:
            GraphStoreWriteConflictError: ``deferred`` is None and a
                relationship is owned by another in-flight job. The
                transaction rolls back.
        """
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
        pending_job_id: UUID | None = None,
        deferred: DeferredWrites | None = None,
    ) -> UpsertResult:
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
            pending_job_id: The in-flight Cutover Job's id. ``pending_job_id``
                tags the rows the call creates, so retrieval skips them until
                the job commits. A write that reaches a row the job did not
                create is not applied and is added to ``deferred``.
            deferred: Receives the records whose rows were not written. The
                commit transaction replays them. Required when
                ``pending_job_id`` is set.

        Returns:
            The number written or deferred, and one failure entry for each
            isolated record.

        Raises:
            ValueError: ``batch_size`` is not positive, or ``deferred`` is
                missing while ``pending_job_id`` is set.
        """

    @abstractmethod
    async def upsert_relations(
        self,
        relations: Sequence[RelationRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
        deferred: DeferredWrites | None = None,
    ) -> UpsertResult:
        """Write or merge relationships between existing nodes.

        Args:
            relations: The relation records to upsert.
            batch_size: Records per backend write call. Must be positive.
            pending_job_id: The in-flight Cutover Job's id. ``pending_job_id``
                tags the relationships the call creates, so retrieval skips
                them until the job commits. A write that reaches a
                relationship the job did not create is not applied and is
                added to ``deferred``.
            deferred: Receives the records whose relationships were not
                written. The commit transaction replays them. Required when
                ``pending_job_id`` is set.

        Returns:
            The number written or deferred, and one failure entry for each
            isolated record.

        Raises:
            ValueError: ``batch_size`` is not positive, or ``deferred`` is
                missing while ``pending_job_id`` is set.
        """

    @abstractmethod
    async def upsert_candidates(
        self,
        candidates: Sequence[CandidateRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
    ) -> UpsertResult:
        """Write candidate nodes and their evidence links.

        Args:
            candidates: Records whose chunks and optional entity endpoints
                should be linked.
            batch_size: Records per backend write call. Must be positive.
            pending_job_id: The job tag for nodes and edges created by this
                write, or None for committed data.

        Returns:
            The number written and one failure for each missing chunk.

        Raises:
            ValueError: ``batch_size`` is not positive.
        """

    @abstractmethod
    async def blocked_candidate_keys(self, keys: Sequence[str]) -> set[str]:
        """Return candidate keys with a committed non-pending record."""

    @abstractmethod
    async def ensure_unique_constraint(
        self, *, label: str, properties: Sequence[str]
    ) -> None:
        """Make a property combination unique across the nodes of a label.

        Does nothing when the constraint already exists. A backend that builds
        constraints in the background returns once this one is usable.

        Args:
            label: The node label.
            properties: The property names whose combination must be unique.

        Raises:
            ValueError: ``properties`` is empty, or a name is not a safe
                identifier.
        """

    @abstractmethod
    async def ensure_vector_index(
        self, *, label: str, vector_property: str, dimensions: int, distance: Distance
    ) -> None:
        """Create a native vector index if it does not exist.

        Args:
            label: The node label to index.
            vector_property: The embedding property name.
            dimensions: The embedding dimension. If the index already exists
                with a different dimension, this raises.
            distance: The distance metric.

        Raises:
            EmbeddingDimensionMismatchError: The index already exists with a
                different dimension than ``dimensions``.
        """

    @abstractmethod
    async def ensure_fulltext_index(
        self, *, label: str, properties: Sequence[str]
    ) -> None:
        """Create a full-text index over node properties if it does not exist.

        The index is built from the node text of the given properties. Its
        name is derived from the label and the properties, so a repeated call
        with the same arguments does nothing.

        Args:
            label: The node label to index.
            properties: The property names to index. Each must be a safe
                identifier.

        Raises:
            ValueError: ``properties`` is empty, or a name is not a safe
                identifier.
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

    @abstractmethod
    async def list_indexes(self, *, timeout: float | None = None) -> list[IndexInfo]:
        """List every index in the database with its readiness.

        Args:
            timeout: Server-side timeout in seconds. None uses the server's
                default.

        Returns:
            One entry per index, including indexes that are still building.
        """

    @abstractmethod
    async def fulltext_search_call(
        self, *, label: str, properties: Sequence[str]
    ) -> SearchCall:
        """Build the Cypher fragment that searches a full-text index.

        Args:
            label: The node label the index covers.
            properties: The indexed property names, as passed to
                ``ensure_fulltext_index``.

        Returns:
            A fragment that yields ``node`` and ``score`` and expects
            ``$fulltext_terms`` and ``$k``.

        Raises:
            ValueError: ``label`` or a property is not a safe identifier.
        """

    @abstractmethod
    async def vector_search_call(
        self, *, label: str, vector_property: str
    ) -> SearchCall:
        """Build the Cypher fragment that searches a vector index.

        Args:
            label: The node label the index covers.
            vector_property: The embedding property name.

        Returns:
            A fragment that yields ``node`` and ``score`` and expects
            ``$vector`` and ``$k``. ``score`` uses the same scale on every
            backend: higher is closer.

        Raises:
            ValueError: ``label`` or ``vector_property`` is not a safe
                identifier.
        """

    def node_write_extra_set(self) -> str:
        """Return extra ``SET`` clauses that every node upsert must carry.

        Returns:
            Clauses for a node upsert query, which can read ``record.properties``,
            or an empty string when the backend stores the properties as given.
        """
        return ""

    def fulltext_copy_set(
        self, alias: str, source: str, properties: Iterable[str]
    ) -> str:
        """Return ``SET`` clauses a backend needs to keep text searchable.

        Args:
            alias: The Cypher variable of the node being written.
            source: A Cypher map expression that holds the written properties.
            properties: The text properties that have a full-text index.

        Returns:
            Clauses to add to the write, or an empty string when the backend
            searches the stored text directly.
        """
        return ""

    def shortest_path_distance_query(self) -> str:
        """Build the Cypher that measures the shortest committed path.

        Returns:
            A parameterized query expecting ``$seed_ids`` and ``$target_ids``
            that returns a ``dist`` for each pair joined by a path.
        """
        return shortest_path_distance_query()

    def vector_value(self, expression: str) -> str:
        """Wrap a Cypher expression that holds an embedding for a property write.

        Args:
            expression: A Cypher expression that evaluates to a list of floats.

        Returns:
            The expression to assign to a vector property. Backends that store
            a plain float list return ``expression`` unchanged.
        """
        return expression

    async def run_in_transaction(
        self, work: Callable[[GraphStoreTransaction], Awaitable[_T]]
    ) -> _T:
        """Run work with a transaction handle and return its result.

        The default implementation passes this store to ``work`` and provides
        no atomicity across calls. Backends may provide a real transaction.
        A transactional backend commits when ``work`` returns and rolls back
        when it raises. A backend may retry transient failures, so ``work``
        must return results rather than change state outside the callback.

        Args:
            work: The reads and writes to run together. Must be safe to retry.

        Returns:
            Whatever ``work`` returns.
        """
        return await work(self)

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
