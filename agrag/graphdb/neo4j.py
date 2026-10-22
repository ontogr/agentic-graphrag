"""Neo4j graph-store backend."""

import asyncio
import re
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from opentelemetry.trace import SpanKind, Tracer

from agrag.common.data_models.graph_record import (
    DeferredWrites,
    NodeRecord,
    RelationRecord,
)
from agrag.common.data_models.index_record import IndexInfo, SearchCall
from agrag.common.data_models.vector_record import Distance
from agrag.common.validation import require_positive_batch_size
from agrag.cypher.entities import (
    NODE_IDENTITY_LABEL,
    PENDING_TAGGED_NODE_LABELS,
    upsert_node_query,
    validate_identifier,
)
from agrag.cypher.relations import upsert_relation_query
from agrag.cypher.schema import (
    candidate_id_constraint_query,
    candidate_key_index_query,
    candidate_state_index_query,
    cutover_job_document_key_constraint_query,
    cutover_job_status_index_query,
    fulltext_index_name,
    fulltext_index_query,
    list_indexes_query,
    merge_alias_constraint_query,
    merge_key_constraint_name,
    merge_key_constraint_query,
    node_id_constraint_name,
    node_id_constraint_query,
    pending_node_index_query,
    pending_relation_index_query,
    relation_id_constraint_name,
    relation_id_constraint_query,
    unique_constraint_query,
    vector_index_name,
    vector_index_query,
)
from agrag.embedding.errors import EmbeddingDimensionMismatchError
from agrag.graphdb.base import GraphStoreTransaction
from agrag.graphdb.cypher_store import (
    CypherGraphStore,
    query_parameter_attributes,
    require_deferred,
)
from agrag.graphdb.errors import (
    GraphStoreConstraintViolationError,
    GraphStoreMissingExtraError,
    GraphStoreWriteConflictError,
)
from agrag.graphdb.serialize import node_params, relation_params
from agrag.graphdb.settings import Neo4jSettings
from agrag.observability import (
    DB_NAMESPACE,
    DB_QUERY_TEXT,
    DB_SYSTEM_NAME,
)


if TYPE_CHECKING:
    from neo4j import AsyncDriver


_EQUIVALENT_SCHEMA_RULE_ERROR = (
    "Neo.ClientError.Schema.EquivalentSchemaRuleAlreadyExists"
)
_T = TypeVar("_T")


_IMPORTING_SUBQUERY = re.compile(
    r"CALL \{ WITH ([A-Za-z_]\w*(?:, [A-Za-z_]\w*)*)(?= [A-Z]|\s)"
)


def scoped_subqueries(query: str) -> str:
    """Rewrite importing ``CALL { WITH x ... }`` subqueries to the scoped form.

    The shared builders write a subquery that imports its variables with a
    leading ``WITH``, the form every supported backend runs. Neo4j 5.23 and
    later report that form as deprecated in favor of ``CALL (x) { ... }``, so
    this store sends the scoped form. Only a ``WITH`` that lists plain variable
    names directly after ``CALL {`` is rewritten.

    Args:
        query: The Cypher text from a builder.

    Returns:
        The query with each such subquery in scoped form.
    """
    return _IMPORTING_SUBQUERY.sub(r"CALL (\1) {", query)


def _settle_transaction_rows(
    query: str,
    batch: Sequence[dict[str, Any]],
    rows: Sequence[dict[str, Any]],
    *,
    deferred: DeferredWrites | None,
) -> None:
    """Defer the records a transactional write left unwritten.

    Without a deferral list, this caller has no job to defer to, so a row
    that another job owns cannot be written. The error rolls the surrounding
    transaction back.
    """
    if deferred is not None:
        deferred.add_unwritten(query, batch, rows)
        return
    if any(row.get("written") is False for row in rows):
        raise GraphStoreWriteConflictError(
            "write reached a row owned by an in-flight job"
        )


class _Neo4jTransaction(GraphStoreTransaction):
    """A ``GraphStoreTransaction`` bound to one managed Neo4j transaction.

    Every ``execute_read``/``execute_write``/``upsert_nodes`` call here runs
    against the same underlying transaction, so they all commit or roll back
    together when the managed transaction finishes.
    """

    def __init__(self, tx: Any, *, store: "Neo4jGraphStore", tracer: Tracer) -> None:
        """Bind this handle to a managed transaction and its owning store.

        Args:
            tx: The Neo4j ``AsyncTransaction`` supplied by the driver.
            store: The store this transaction belongs to, used for label and
                relation-type bookkeeping and for ensuring each relationship
                type's identity constraint exists before its first write.
            tracer: Opens this handle's own spans. Passed explicitly by
                ``run_in_transaction()`` rather than read off ``store`` -- this
                class does not otherwise touch ``store``'s private state.
        """
        self._tx = tx
        self._store = store
        self._tracer = tracer

    async def execute_read(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a read against this transaction and return its rows."""
        attributes = {
            DB_SYSTEM_NAME: "neo4j",
            DB_QUERY_TEXT: query,
            "agrag.transactional": True,
            **query_parameter_attributes(parameters),
        }
        with self._tracer.start_as_current_span(
            "agrag.graphdb.execute_read",
            kind=SpanKind.CLIENT,
            attributes=attributes,
        ):
            result = await self._tx.run(scoped_subqueries(query), parameters or {})
            return await result.data()

    async def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a write against this transaction and return its rows."""
        attributes = {
            DB_SYSTEM_NAME: "neo4j",
            DB_QUERY_TEXT: query,
            "agrag.transactional": True,
            **query_parameter_attributes(parameters),
        }
        with self._tracer.start_as_current_span(
            "agrag.graphdb.execute_write",
            kind=SpanKind.CLIENT,
            attributes=attributes,
        ):
            result = await self._tx.run(scoped_subqueries(query), parameters or {})
            return await result.data()

    async def upsert_nodes(
        self,
        label: str,
        nodes: Sequence[NodeRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
        deferred: DeferredWrites | None = None,
    ) -> None:
        """Write or merge nodes against this transaction.

        Mirrors ``Neo4jGraphStore.upsert_nodes``, minus the identity
        constraint check: ``run_in_transaction()`` ensures it before invoking
        the callback, so no write inside it needs to repeat the check.

        Raises:
            ValueError: ``batch_size`` is not positive, or ``deferred`` is
                missing while ``pending_job_id`` is set.
            GraphStoreWriteConflictError: A row is owned by another job and
                ``deferred`` is None.
        """
        require_deferred(pending_job_id, deferred)
        require_positive_batch_size(batch_size)
        await self._store.register_labels([label])
        groups: dict[tuple[str, ...], list[NodeRecord]] = defaultdict(list)
        for node in nodes:
            labels = tuple(sorted(set(node.labels)))
            groups[labels].append(node)
        for labels, group_nodes in groups.items():
            await self._store.register_labels(labels)
            query = upsert_node_query(labels)
            records = [
                node_params(n, pending_job_id=pending_job_id) for n in group_nodes
            ]
            for start in range(0, len(records), batch_size):
                batch = records[start : start + batch_size]
                rows = await self.execute_write(query, {"records": batch})
                _settle_transaction_rows(query, batch, rows, deferred=deferred)

    async def upsert_relations(
        self,
        relations: Sequence[RelationRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
        deferred: DeferredWrites | None = None,
    ) -> None:
        """Write or merge relationships against this transaction.

        Mirrors ``Neo4jGraphStore.upsert_relations``, including its per-type
        constraint check, but via ``self.execute_write`` so every write joins
        the surrounding managed transaction.

        Raises:
            ValueError: ``batch_size`` is not positive, or ``deferred`` is
                missing while ``pending_job_id`` is set.
            GraphStoreWriteConflictError: A relationship is owned by another
                job and ``deferred`` is None.
        """
        require_deferred(pending_job_id, deferred)
        require_positive_batch_size(batch_size)
        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for rel in relations:
            validate_identifier(rel.type)
            by_type[rel.type].append(
                relation_params(rel, pending_job_id=pending_job_id)
            )
        for rel_type, params in by_type.items():
            await self._store.ensure_relation_constraint(rel_type)
            await self._store.register_relation_types([rel_type])
            query = upsert_relation_query(rel_type)
            for start in range(0, len(params), batch_size):
                batch = params[start : start + batch_size]
                rows = await self.execute_write(query, {"records": batch})
                _settle_transaction_rows(query, batch, rows, deferred=deferred)


class Neo4jGraphStore(CypherGraphStore):
    """A ``GraphStore`` backed by Neo4j, using native vector indexes.

    The driver connects lazily on first use, so constructing the store does not
    open a network connection. ``execute_read``/``execute_write`` wrap the
    driver's managed transactions with no added retry loop.
    """

    def __init__(
        self,
        *,
        settings: Neo4jSettings | None = None,
        driver: "AsyncDriver | None" = None,
        tracer: Tracer | None = None,
    ) -> None:
        """Build the store.

        Args:
            settings: Neo4j connection settings. Defaults to ``Neo4jSettings()``.
            driver: A pre-built ``AsyncDriver``, for tests. When set,
                ``__init__`` imports nothing and the store calls this object
                directly instead of building one.
            tracer: Opens every span this store's methods produce.
        """
        super().__init__(tracer=tracer)
        self._settings = settings or Neo4jSettings()
        self._driver: Any = driver
        self._driver_lock = asyncio.Lock()
        self._identity_constraint_ready = False
        self._identity_constraint_lock = asyncio.Lock()
        self._merge_alias_constraint_ready = False
        self._merge_alias_constraint_lock = asyncio.Lock()
        self._cutover_job_constraint_ready = False
        self._cutover_job_constraint_lock = asyncio.Lock()
        self._cutover_job_status_index_ready = False
        self._cutover_job_status_index_lock = asyncio.Lock()
        self._pending_tag_indexes_ready = False
        self._pending_tag_indexes_lock = asyncio.Lock()
        self._candidate_schema_ready = False
        self._candidate_schema_lock = asyncio.Lock()
        self._relation_type_constraints_ready: set[str] = set()
        self._relation_constraint_lock = asyncio.Lock()

    async def _ensure_driver(self) -> "AsyncDriver":
        """Build the Neo4j driver once and cache it.

        Concurrent first calls are serialized on ``_driver_lock`` so only one
        of them builds the driver, rather than each racing to construct its
        own.

        Returns:
            The connected driver object.

        Raises:
            GraphStoreMissingExtraError: the neo4j driver is not installed.
        """
        if self._driver is not None:
            return self._driver
        async with self._driver_lock:
            if self._driver is not None:
                return self._driver
            with self._tracer.start_as_current_span(
                "agrag.graphdb.build_driver", kind=SpanKind.INTERNAL
            ):
                try:
                    # Lazy import: a clean install must raise
                    # GraphStoreMissingExtraError, not ImportError, when neo4j is
                    # absent.
                    from neo4j import (  # noqa: PLC0415
                        AsyncGraphDatabase,
                        NotificationDisabledClassification,
                    )
                except ImportError as exc:
                    raise GraphStoreMissingExtraError("neo4j") from exc
                self._driver = AsyncGraphDatabase.driver(
                    self._settings.uri,
                    auth=(
                        self._settings.username,
                        self._settings.password.get_secret_value(),
                    ),
                    max_connection_lifetime=self._settings.max_connection_lifetime,
                    # The store probes labels and property keys that a new
                    # database does not have yet. The server reports each probe
                    # as UNRECOGNIZED, which is expected noise. Other
                    # classifications, such as PERFORMANCE and DEPRECATION,
                    # still reach the neo4j.notifications logger.
                    notifications_disabled_classifications=[
                        NotificationDisabledClassification.UNRECOGNIZED
                    ],
                )
        return self._driver

    async def connect(self) -> None:
        """Open the driver and verify connectivity."""
        driver = await self._ensure_driver()
        await driver.verify_connectivity()

    async def close(self) -> None:
        """Close the driver, releasing its connection pool."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    def session(self) -> AbstractAsyncContextManager[Any]:
        """Open a session to the configured database."""
        return self._driver.session(database=self._settings.database)

    async def execute_read(
        self,
        query: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        """Run a read transaction and return its rows.

        Args:
            query: The Cypher query to run.
            parameters: The query parameters.
            timeout: Server-side transaction timeout in seconds,
                applied through the driver's ``unit_of_work`` so the
                database terminates the transaction when it runs
                longer. None uses the server's default timeout.

        Returns:
            The result rows as dicts.
        """
        attributes: dict[str, Any] = {
            DB_SYSTEM_NAME: "neo4j",
            DB_NAMESPACE: self._settings.database,
            DB_QUERY_TEXT: query,
            **query_parameter_attributes(parameters),
        }
        with self._tracer.start_as_current_span(
            "agrag.graphdb.execute_read",
            kind=SpanKind.CLIENT,
            attributes=attributes,
        ):
            async with self.session() as s:
                if timeout is None:
                    return await s.execute_read(
                        self._run, scoped_subqueries(query), parameters or {}
                    )
                from neo4j import unit_of_work  # noqa: PLC0415

                return await s.execute_read(
                    unit_of_work(timeout=timeout)(self._run),
                    scoped_subqueries(query),
                    parameters or {},
                )

    async def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a write transaction and return its rows.

        Raises:
            GraphStoreConstraintViolationError: The write violated a uniqueness
                constraint, translated from the driver's own exception so
                callers do not need a hard dependency on it.
        """
        from neo4j.exceptions import ConstraintError  # noqa: PLC0415

        attributes: dict[str, Any] = {
            DB_SYSTEM_NAME: "neo4j",
            DB_NAMESPACE: self._settings.database,
            DB_QUERY_TEXT: query,
            **query_parameter_attributes(parameters),
        }
        with self._tracer.start_as_current_span(
            "agrag.graphdb.execute_write",
            kind=SpanKind.CLIENT,
            attributes=attributes,
        ):
            async with self.session() as s:
                try:
                    return await s.execute_write(
                        self._run, scoped_subqueries(query), parameters or {}
                    )
                except ConstraintError as exc:
                    raise GraphStoreConstraintViolationError(str(exc)) from exc

    @staticmethod
    async def _run(
        tx: Any, query: str, parameters: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        """Run a single query inside a managed transaction and read its rows."""
        result = await tx.run(query, parameters)
        return await result.data()

    async def run_in_transaction(
        self, work: Callable[[GraphStoreTransaction], Awaitable[_T]]
    ) -> _T:
        """Run work in a Neo4j managed transaction and return its result.

        Neo4j may retry ``work`` after a transient failure. The callback must
        therefore be safe to run again and must return results rather than
        mutate state outside the callback.

        Args:
            work: The reads and writes to run together. Must be safe to retry.

        Returns:
            Whatever ``work`` returns.

        Raises:
            GraphStoreConstraintViolationError: The transaction violated a
                uniqueness constraint.
        """
        from neo4j.exceptions import ConstraintError  # noqa: PLC0415

        with self._tracer.start_as_current_span(
            "agrag.graphdb.transaction", kind=SpanKind.INTERNAL
        ):
            await self._ensure_identity_constraint()
            await self._ensure_merge_alias_constraint()
            await self._ensure_cutover_job_constraint()
            await self._ensure_cutover_job_status_index()
            await self._ensure_pending_tag_indexes()
            await self._ensure_candidate_schema()
            async with self.session() as session:
                try:

                    async def run_work(tx: Any) -> _T:
                        return await work(
                            _Neo4jTransaction(tx, store=self, tracer=self._tracer)
                        )

                    return await session.execute_write(run_work)
                except ConstraintError as exc:
                    raise GraphStoreConstraintViolationError(str(exc)) from exc

    async def setup_constraints(self) -> None:
        """Create ``id`` and ``merge_key`` uniqueness constraints per label.

        "Known" means written by this instance or already present in the
        database, so a fresh store can set up constraints for an existing
        database without first rewriting every record. The ``id`` constraint
        backs node identity; ``merge_key`` prevents concurrent ingestion from
        creating duplicate canonical entities. Also creates the global
        uniqueness constraint on ``NODE_IDENTITY_LABEL`` that
        ``upsert_node_query``'s ``MERGE`` relies on to resolve a node by id
        regardless of its other, mutable labels, and a per-type uniqueness
        constraint on ``id`` for every known relationship type, which backs
        the stale-relationship cleanup ``upsert_relation_query`` performs on
        endpoint changes.

        Also creates the range indexes on the pending tag property
        (``_pending_job_id``) that commit and rollback use to find a job's
        rows: one per label in ``PENDING_TAGGED_NODE_LABELS`` and one per
        known relationship type. The CutoverJob status index and the
        candidate schema are created here as well.
        """
        await self._ensure_identity_constraint()
        await self._ensure_merge_alias_constraint()
        await self._ensure_cutover_job_constraint()
        await self._ensure_cutover_job_status_index()
        await self._ensure_pending_tag_indexes()
        await self._ensure_candidate_schema()
        # Read the existing names once so the cost does not grow with the
        # number of constraints already in the database. Creates keep
        # IF NOT EXISTS because another writer can create one in between.
        rows = await self.execute_read("SHOW CONSTRAINTS YIELD name RETURN name")
        existing = {row["name"] for row in rows}
        for label in await self._all_labels():
            if node_id_constraint_name(label) not in existing:
                await self.execute_write(node_id_constraint_query(label))
            # Merge-key uniqueness backs concurrent add() safety: two writers for
            # the same (label, normalized name) cannot both create a canonical.
            if merge_key_constraint_name(label) not in existing:
                await self.execute_write(merge_key_constraint_query(label))
        for rel_type in await self._all_relation_types():
            if relation_id_constraint_name(rel_type) in existing:
                await self.execute_write(pending_relation_index_query(rel_type))
                self._relation_type_constraints_ready.add(rel_type)
                continue
            await self._ensure_relation_constraint(rel_type)

    async def _ensure_identity_constraint(self) -> None:
        """Create the ``NODE_IDENTITY_LABEL`` uniqueness constraint once.

        Neo4j only makes ``MERGE`` atomic under concurrent writers once a
        uniqueness constraint backs the merged property; without it, two
        concurrent ``upsert_nodes`` calls for the same id can each find no
        match and create separate nodes. Creating the constraint here, not
        only in ``setup_constraints``, closes that window for callers that
        upsert before running setup, and the lock serializes concurrent first
        calls so only one of them issues the ``CREATE CONSTRAINT``.
        """
        if self._identity_constraint_ready:
            return
        async with self._identity_constraint_lock:
            if self._identity_constraint_ready:
                return
            await self.execute_write(node_id_constraint_query(NODE_IDENTITY_LABEL))
            self._identity_constraint_ready = True

    async def _ensure_merge_alias_constraint(self) -> None:
        """Create the merge-key alias table's uniqueness constraint once.

        Backs ``upsert_merge_alias_query``'s ``MERGE`` the same way
        ``_ensure_identity_constraint`` backs node upserts: without it, two
        concurrent writers recording an alias for the same merge_key for the
        first time could each find no match and create separate alias nodes.
        """
        if self._merge_alias_constraint_ready:
            return
        async with self._merge_alias_constraint_lock:
            if self._merge_alias_constraint_ready:
                return
            await self.execute_write(merge_alias_constraint_query())
            self._merge_alias_constraint_ready = True

    async def _ensure_cutover_job_constraint(self) -> None:
        """Create the CutoverJob document_key uniqueness constraint once.

        Backs ``acquire_lease_query``'s ``MERGE`` the same way
        ``_ensure_identity_constraint`` backs node upserts: without it, two
        concurrent first-time acquirers for the same document_key could each
        find no match and create separate job nodes.
        """
        if self._cutover_job_constraint_ready:
            return
        async with self._cutover_job_constraint_lock:
            if self._cutover_job_constraint_ready:
                return
            await self.execute_write(cutover_job_document_key_constraint_query())
            self._cutover_job_constraint_ready = True

    async def _ensure_cutover_job_status_index(self) -> None:
        """Create the CutoverJob status index once for recovery scans."""
        if self._cutover_job_status_index_ready:
            return
        async with self._cutover_job_status_index_lock:
            if self._cutover_job_status_index_ready:
                return
            await self.execute_write(cutover_job_status_index_query())
            self._cutover_job_status_index_ready = True

    async def _ensure_pending_tag_indexes(self) -> None:
        """Create the pending-tag node indexes once for commit and rollback."""
        if self._pending_tag_indexes_ready:
            return
        async with self._pending_tag_indexes_lock:
            if self._pending_tag_indexes_ready:
                return
            for label in PENDING_TAGGED_NODE_LABELS:
                await self.execute_write(pending_node_index_query(label))
            self._pending_tag_indexes_ready = True

    async def _ensure_candidate_schema(self) -> None:
        """Create candidate constraints and indexes once."""
        if self._candidate_schema_ready:
            return
        async with self._candidate_schema_lock:
            if self._candidate_schema_ready:
                return
            await self.execute_write(candidate_id_constraint_query())
            await self.execute_write(candidate_key_index_query())
            await self.execute_write(candidate_state_index_query())
            self._candidate_schema_ready = True

    async def _ensure_relation_constraint(self, rel_type: str) -> None:
        """Create a relationship type's ``id`` uniqueness constraint once.

        Relationship identity is each record's ``id``, and
        ``upsert_relation_query``'s ``MERGE`` on that id is only atomic under
        concurrent writers once a uniqueness constraint backs it; without
        one, two concurrent ``upsert_relations`` calls for the same id and
        type can each find no match and create a duplicate relationship.
        Creating the constraint here, not only in ``setup_constraints``,
        closes that window for callers that upsert before running setup, and
        the lock serializes concurrent first calls so only one of them
        issues the ``CREATE CONSTRAINT`` for a given type.

        Args:
            rel_type: The relationship type to ensure a constraint for. Must
                already be validated.
        """
        if rel_type in self._relation_type_constraints_ready:
            return
        async with self._relation_constraint_lock:
            if rel_type in self._relation_type_constraints_ready:
                return
            await self.execute_write(relation_id_constraint_query(rel_type))
            await self.execute_write(pending_relation_index_query(rel_type))
            self._relation_type_constraints_ready.add(rel_type)

    async def ensure_relation_constraint(self, rel_type: str) -> None:
        """Create a relationship type's ``id`` uniqueness constraint once.

        Public entry point onto ``_ensure_relation_constraint`` for
        ``_Neo4jTransaction.upsert_relations``, which must give the same
        constraint-before-first-write guarantee inside an explicit
        transaction that the non-transactional ``upsert_relations`` gives.

        Args:
            rel_type: The relationship type to ensure a constraint for. Must
                already be validated.
        """
        await self._ensure_relation_constraint(rel_type)

    async def setup_indexes(self) -> None:
        """Set up indexes now provided by the store's uniqueness constraints.

        Kept as a no-op for callers that provision constraints and indexes in
        separate steps. Neo4j creates backing indexes for the ``id`` and
        ``merge_key`` uniqueness constraints, so creating range indexes for
        the same properties would conflict with those constraints.
        """

    async def ensure_unique_constraint(
        self, *, label: str, properties: Sequence[str]
    ) -> None:
        """Make a property combination unique across the nodes of a label."""
        from neo4j.exceptions import ClientError  # noqa: PLC0415

        query = unique_constraint_query(label, properties)
        try:
            await self.execute_write(query)
        except ClientError as exc:
            if exc.code != _EQUIVALENT_SCHEMA_RULE_ERROR:
                raise

    async def ensure_vector_index(
        self, *, label: str, vector_property: str, dimensions: int, distance: Distance
    ) -> None:
        """Create a native vector index if it does not exist.

        A concurrent creator can commit the same index after this operation
        starts. Neo4j reports that race as an equivalent-schema error, which
        means the requested index already exists.

        Raises:
            EmbeddingDimensionMismatchError: The index already exists with a
                different dimension than ``dimensions``.
        """
        from neo4j.exceptions import ClientError  # noqa: PLC0415

        validate_identifier(label)
        validate_identifier(vector_property)
        self._known_labels.add(label)
        try:
            await self.execute_write(
                vector_index_query(label, vector_property, dimensions, distance)
            )
        except ClientError as exc:
            if exc.code != _EQUIVALENT_SCHEMA_RULE_ERROR:
                raise
        # CREATE ... IF NOT EXISTS keeps an existing index of the same name as
        # it is, so a wrong-size embedder would otherwise write vectors the
        # index never returns.
        name = vector_index_name(label, vector_property)
        for index in await self.list_indexes():
            if index.name == name and index.dimensions != dimensions:
                raise EmbeddingDimensionMismatchError(
                    expected=index.dimensions or 0, actual=dimensions
                )

    async def list_indexes(self, *, timeout: float | None = None) -> list[IndexInfo]:
        """List every index in the database with its readiness."""
        rows = await self.execute_read(list_indexes_query(), timeout=timeout)
        return [
            IndexInfo(
                name=row["name"],
                state=row["state"],
                population_percent=row["populationPercent"],
                type=row["type"],
                labels=list(row["labelsOrTypes"] or []),
                properties=list(row["properties"] or []),
                dimensions=(row["options"] or {})
                .get("indexConfig", {})
                .get("vector.dimensions"),
            )
            for row in rows
        ]

    async def fulltext_search_call(
        self, *, label: str, properties: Sequence[str]
    ) -> SearchCall:
        """Build the Cypher fragment that searches a full-text index."""
        return SearchCall(
            "CALL db.index.fulltext.queryNodes($index, $fulltext_terms, "
            "{limit: $k}) YIELD node, score",
            {"index": fulltext_index_name(label, properties)},
        )

    async def vector_search_call(
        self, *, label: str, vector_property: str
    ) -> SearchCall:
        """Build the Cypher fragment that searches a vector index."""
        return SearchCall(
            "CALL db.index.vector.queryNodes($index, $k, $vector) YIELD node, score",
            {"index": vector_index_name(label, vector_property)},
        )

    async def ensure_fulltext_index(
        self, *, label: str, properties: Sequence[str]
    ) -> None:
        """Create a full-text index over node properties if it does not exist.

        A concurrent creator can commit the same index after this operation
        starts. Neo4j reports that race as an equivalent-schema error, which
        means the requested index already exists.
        """
        from neo4j.exceptions import ClientError  # noqa: PLC0415

        query = fulltext_index_query(label, properties)
        self._known_labels.add(label)
        try:
            await self.execute_write(query)
        except ClientError as exc:
            if exc.code != _EQUIVALENT_SCHEMA_RULE_ERROR:
                raise

    @staticmethod
    def _is_missing_index_error(exc: Exception) -> bool:
        """Return whether a search failed because the index does not exist."""
        return "no such vector schema index" in str(exc)

    @staticmethod
    def _is_record_specific_error(exc: Exception) -> bool:
        """Return whether a Neo4j error can be caused by one record."""
        from neo4j.exceptions import CypherTypeError  # noqa: PLC0415

        if isinstance(exc, GraphStoreConstraintViolationError):
            return True
        return isinstance(exc, CypherTypeError)
