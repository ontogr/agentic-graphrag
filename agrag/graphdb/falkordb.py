"""FalkorDB graph-store backend."""

import asyncio
import contextlib
import contextvars
import re
from collections.abc import (
    AsyncIterator,
    Awaitable,
    Callable,
    Iterable,
    Mapping,
    Sequence,
)
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from opentelemetry.trace import SpanKind, Tracer

from agrag.common.data_models.candidate import CANDIDATE_LABEL
from agrag.common.data_models.cutover_job import (
    CUTOVER_JOB_LABEL,
)
from agrag.common.data_models.graph_record import (
    PENDING_JOB_ID_PROPERTY,
    DeferredWrites,
    NodeRecord,
    RelationRecord,
    UpsertFailure,
    UpsertResult,
)
from agrag.common.data_models.index_record import (
    INDEX_STATE_ONLINE,
    IndexInfo,
    SearchCall,
)
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import (
    MERGE_ALIAS_LABEL,
    NODE_IDENTITY_LABEL,
    PENDING_TAGGED_NODE_LABELS,
    validate_identifier,
    validate_identifier_syntax,
)
from agrag.cypher.relations import shortest_path_distance_query
from agrag.cypher.schema import fulltext_index_name, vector_index_name
from agrag.embedding.errors import EmbeddingDimensionMismatchError
from agrag.graphdb.base import GraphStoreTransaction
from agrag.graphdb.cypher_store import CypherGraphStore, query_parameter_attributes
from agrag.graphdb.errors import (
    GraphStoreConstraintViolationError,
    GraphStoreError,
    GraphStoreMissingExtraError,
    GraphStoreWriteConflictError,
)
from agrag.graphdb.settings import FalkorDBSettings
from agrag.observability import (
    DB_NAMESPACE,
    DB_QUERY_TEXT,
    DB_SYSTEM_NAME,
)


if TYPE_CHECKING:
    from falkordb.asyncio import FalkorDB


_T = TypeVar("_T")

# The lowest FalkorDB graph module version the store is tested against.
MIN_MODULE_VERSION = 42202

# The longest path, in relationships, the path-distance query searches.
MAX_PATH_HOPS = 5

_SCHEMA_POLL_SECONDS = 0.1
_SCHEMA_TIMEOUT_SECONDS = 60.0
_DEFAULT_VECTOR_PROPERTIES = frozenset({"embedding"})

_SIMILARITY: dict[Distance, str] = {
    Distance.COSINE: "cosine",
    Distance.EUCLID: "euclidean",
}

# The server reply for a read against a graph that was never written.
_EMPTY_KEY = "Invalid graph operation on empty key"

# FalkorDB's full-text tokenizer does not split words at a line break, so the
# words next to one are never found. Each indexed text property is mirrored into
# a property with line breaks replaced by spaces, and the mirror is what the
# index covers. Results hide the mirrors again.
_SEARCH_COPY_PREFIX = "_ft_"

_RANGE = "RANGE"
_FULLTEXT = "FULLTEXT"
_VECTOR = "VECTOR"

_RECORD_SPECIFIC_MESSAGES = (
    "Property values can only be of primitive types",
    "Type mismatch",
)


@dataclass(frozen=True)
class _SchemaObject:
    """One index, or one uniqueness constraint with the index it needs.

    Attributes:
        target: The node label or relationship type.
        properties: The properties the object covers. A uniqueness constraint
            makes the combination unique.
        relationship: True when ``target`` is a relationship type.
        unique: True for a uniqueness constraint, False for a plain index.
    """

    target: str
    properties: tuple[str, ...]
    relationship: bool = False
    unique: bool = False


def _plain(value: Any) -> Any:
    """Convert a FalkorDB result value to the plain shape other stores return.

    Nodes and relationships become their property dicts, as the Neo4j driver's
    ``data()`` does, and containers are converted recursively.
    """
    from falkordb.edge import Edge  # noqa: PLC0415
    from falkordb.node import Node  # noqa: PLC0415
    from falkordb.path import Path  # noqa: PLC0415

    if isinstance(value, (Node, Edge)):
        return {
            key: _plain(item)
            for key, item in value.properties.items()
            if not key.startswith(_SEARCH_COPY_PREFIX)
        }
    if isinstance(value, Path):
        parts: list[Any] = []
        for index, node in enumerate(value.nodes()):
            parts.append(_plain(node))
            if index < len(value.edges()):
                parts.append(_plain(value.edges()[index]))
        return parts
    if isinstance(value, Mapping):
        return {
            key: _plain(item)
            for key, item in value.items()
            if not str(key).startswith(_SEARCH_COPY_PREFIX)
        }
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _index_kinds(row: Mapping[str, Any]) -> dict[str, list[str]]:
    """Return the index kinds of each property in one ``db.indexes()`` row.

    The ``types`` column is empty for a property that no node has been written
    with yet, so the kinds come from the index field paths: ``range:<name>``,
    ``vector:<name>``, or the bare name of a full-text field.
    """
    paths = {
        str(field.get("path"))
        for field in (row.get("info") or {}).get("fields", [])
        if isinstance(field, Mapping)
    }
    kinds: dict[str, list[str]] = {}
    for prop in row["properties"]:
        found = []
        if f"range:{prop}" in paths:
            found.append(_RANGE)
        if f"vector:{prop}" in paths:
            found.append(_VECTOR)
        if prop in paths:
            found.append(_FULLTEXT)
        if found:
            kinds[prop] = found
    return kinds


def _union_terms(text: str) -> str:
    """Turn search text into a query that matches any of its words.

    FalkorDB's full-text search requires every word of a plain query, while the
    search legs expect a match on any word, ranked by how many match. Joining
    the words with ``|`` asks for that, and keeping only word characters leaves
    no operator for the query parser to read.

    Returns:
        The words joined by ``|``, or an empty string when the text has none.
    """
    return "|".join(re.findall(r"\w+", text))


def _parameter(value: Any) -> Any:
    """Convert a query parameter to a value the FalkorDB client can inline."""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        return {key: _parameter(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_parameter(item) for item in value]
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


class _ReentrantGuard:
    """An asyncio lock that a task already holding it can take again."""

    def __init__(self) -> None:
        """Create an unlocked guard."""
        self._lock = asyncio.Lock()
        self._held: contextvars.ContextVar[bool] = contextvars.ContextVar(
            "falkordb_guard_held", default=False
        )

    @asynccontextmanager
    async def hold(self) -> AsyncIterator[None]:
        """Hold the lock, or pass straight through when this task holds it."""
        if self._held.get():
            yield
            return
        async with self._lock:
            token = self._held.set(True)
            try:
                yield
            finally:
                self._held.reset(token)


class _FalkorDBTransaction(GraphStoreTransaction):
    """A ``GraphStoreTransaction`` over a FalkorDB store.

    FalkorDB runs each query atomically on its own and has no multi-statement
    transaction, so the statements of one callback run in order and are not
    rolled back together. A write that reaches a row owned by another job, or
    any record the store would otherwise isolate, raises here the way a
    Neo4j transaction does.
    """

    def __init__(self, store: "FalkorDBGraphStore") -> None:
        """Bind this handle to its store."""
        self._store = store

    def vector_value(self, expression: str) -> str:
        """Wrap a float-list expression so FalkorDB stores it as a vector."""
        return self._store.vector_value(expression)

    def fulltext_copy_set(
        self, alias: str, source: str, properties: Iterable[str]
    ) -> str:
        """Return the clauses that keep the search copies of written text."""
        return self._store.fulltext_copy_set(alias, source, properties)

    async def execute_read(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a read in the surrounding callback."""
        return await self._store.execute_read(query, parameters)

    async def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a write in the surrounding callback."""
        return await self._store.execute_write(query, parameters)

    async def upsert_nodes(
        self,
        label: str,
        nodes: Sequence[NodeRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
        deferred: DeferredWrites | None = None,
    ) -> None:
        """Write or merge nodes, raising for any record the store isolated."""
        outcome = await self._store.upsert_nodes(
            label,
            nodes,
            batch_size=batch_size,
            pending_job_id=pending_job_id,
            deferred=deferred,
        )
        _raise_for_failures(outcome)

    async def upsert_relations(
        self,
        relations: Sequence[RelationRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
        deferred: DeferredWrites | None = None,
    ) -> None:
        """Write or merge relationships, raising for any record isolated."""
        outcome = await self._store.upsert_relations(
            relations,
            batch_size=batch_size,
            pending_job_id=pending_job_id,
            deferred=deferred,
        )
        _raise_for_failures(outcome)


def _raise_for_failures(outcome: UpsertResult) -> None:
    """Raise for the first failure of a write that must not isolate records."""
    for failure in outcome.failures:
        if failure.error_type == "PendingRowConflict":
            raise GraphStoreWriteConflictError(
                "write reached a row owned by an in-flight job"
            )
        raise GraphStoreError(f"{failure.error_type}: {failure.error_message}")


class FalkorDBGraphStore(CypherGraphStore):
    """A ``GraphStore`` backed by FalkorDB, using native vector indexes.

    The client connects lazily on first use, so constructing the store does not
    open a network connection. Each query is atomic on its own. A callback
    passed to ``run_in_transaction`` runs its statements in order with no
    rollback, so callers keep every statement of such a group safe to repeat.
    """

    def __init__(
        self,
        *,
        settings: FalkorDBSettings | None = None,
        client: "FalkorDB | None" = None,
        tracer: Tracer | None = None,
    ) -> None:
        """Build the store.

        Args:
            settings: Connection settings. Defaults to ``FalkorDBSettings()``.
            client: A pre-built ``falkordb.asyncio.FalkorDB`` client, for tests.
            tracer: Opens every span this store's methods produce.
        """
        super().__init__(tracer=tracer)
        self._settings = settings or FalkorDBSettings()
        self._client: Any = client
        self._pool: Any = None
        self._graph: Any = client.select_graph(self._settings.graph) if client else None
        self._client_lock = asyncio.Lock()
        self._schema_ready: set[str] = set()
        self._schema_lock = asyncio.Lock()
        self._vector_properties: set[str] = set(_DEFAULT_VECTOR_PROPERTIES)
        self._fulltext_properties: set[str] = set()
        self._vector_similarity: dict[tuple[str, str], str] = {}
        self._vector_dimensions: dict[tuple[str, str], int] = {}
        self._transaction_guard = _ReentrantGuard()

    async def _ensure_client(self) -> Any:
        """Build the client once and cache it.

        Raises:
            GraphStoreMissingExtraError: The falkordb package is not installed.
        """
        if self._client is not None:
            return self._client
        async with self._client_lock:
            if self._client is not None:
                return self._client
            with self._tracer.start_as_current_span(
                "agrag.graphdb.build_driver", kind=SpanKind.INTERNAL
            ):
                try:
                    from falkordb.asyncio import FalkorDB  # noqa: PLC0415
                    from redis.asyncio import BlockingConnectionPool  # noqa: PLC0415
                except ImportError as exc:
                    raise GraphStoreMissingExtraError("falkordb") from exc
                password = self._settings.password
                pool = BlockingConnectionPool.from_url(
                    self._settings.url,
                    max_connections=self._settings.max_connections,
                    timeout=None,
                    decode_responses=True,
                    password=password.get_secret_value() if password else None,
                )
                self._pool = pool
                self._client = FalkorDB(connection_pool=pool)
                self._graph = self._client.select_graph(self._settings.graph)
        return self._client

    async def connect(self) -> None:
        """Open the client and verify connectivity and server settings.

        Raises:
            GraphStoreError: The server module is older than the tested minimum,
                or a server limit would silently cut results.
        """
        client = await self._ensure_client()
        await client.connection.ping()
        modules = await client.connection.execute_command("MODULE", "LIST")
        version = _graph_module_version(modules)
        if version is None or version < MIN_MODULE_VERSION:
            raise GraphStoreError(
                f"FalkorDB graph module {version} is older than {MIN_MODULE_VERSION}"
            )
        for index in await self.list_indexes():
            if index.type == _FULLTEXT:
                self._fulltext_properties.update(index.properties)
            elif index.type == _VECTOR:
                self._vector_properties.update(index.properties)
        if await client.config_get("RESULTSET_SIZE") != -1:
            raise GraphStoreError(
                "FalkorDB RESULTSET_SIZE is finite, so queries would silently "
                "drop rows; start the server with FALKORDB_ARGS='RESULTSET_SIZE -1'"
            )

    async def close(self) -> None:
        """Close the client, releasing its connection pool."""
        if self._client is not None:
            await self._client.aclose()
            if self._pool is not None:
                await self._pool.aclose()
                self._pool = None
            self._client = None
            self._graph = None

    def session(self) -> AbstractAsyncContextManager[Any]:
        """Open a session. FalkorDB has none, so the session is the store."""
        return contextlib.nullcontext(self)

    async def _run(
        self,
        query: str,
        parameters: Mapping[str, Any] | None,
        *,
        read_only: bool,
        timeout: float | None,
    ) -> list[dict[str, Any]]:
        """Run one query and return its rows as dicts."""
        await self._ensure_client()
        params = _parameter(dict(parameters)) if parameters else None
        if params and "fulltext_terms" in params:
            terms = _union_terms(str(params["fulltext_terms"]))
            if not terms:
                return []
            params["fulltext_terms"] = terms
        milliseconds = None if timeout is None else max(1, int(timeout * 1000))
        run = self._graph.ro_query if read_only else self._graph.query
        try:
            result = await run(query, params, timeout=milliseconds)
        except Exception as exc:
            # A graph exists only after its first write, so a read before then
            # has nothing to return, as on an empty Neo4j database.
            if read_only and _EMPTY_KEY in str(exc):
                return []
            raise
        names = [column[1] for column in result.header]
        return [
            dict(zip(names, (_plain(value) for value in row), strict=False))
            for row in result.result_set
        ]

    async def execute_read(
        self,
        query: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        """Run a read query and return its rows.

        Args:
            query: The Cypher query to run.
            parameters: The query parameters.
            timeout: Server-side timeout in seconds. The database stops the query
                when it runs longer. None uses the server's default.

        Returns:
            The result rows as dicts.
        """
        attributes: dict[str, Any] = {
            DB_SYSTEM_NAME: "falkordb",
            DB_NAMESPACE: self._settings.graph,
            DB_QUERY_TEXT: query,
            **query_parameter_attributes(parameters),
        }
        with self._tracer.start_as_current_span(
            "agrag.graphdb.execute_read",
            kind=SpanKind.CLIENT,
            attributes=attributes,
        ):
            return await self._run(query, parameters, read_only=True, timeout=timeout)

    async def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a write query and return its rows.

        Raises:
            GraphStoreConstraintViolationError: The write violated a uniqueness
                constraint.
        """
        attributes: dict[str, Any] = {
            DB_SYSTEM_NAME: "falkordb",
            DB_NAMESPACE: self._settings.graph,
            DB_QUERY_TEXT: query,
            **query_parameter_attributes(parameters),
        }
        with self._tracer.start_as_current_span(
            "agrag.graphdb.execute_write",
            kind=SpanKind.CLIENT,
            attributes=attributes,
        ):
            try:
                return await self._run(query, parameters, read_only=False, timeout=None)
            except Exception as exc:
                if _is_constraint_violation(exc):
                    raise GraphStoreConstraintViolationError(str(exc)) from exc
                raise

    async def run_in_transaction(
        self, work: Callable[[GraphStoreTransaction], Awaitable[_T]]
    ) -> _T:
        """Run work with a transaction handle and return its result.

        The statements run in order, one after the other from this process,
        and are not rolled back if a later one fails. Keep every statement of
        ``work`` safe to repeat.

        Args:
            work: The reads and writes to run together.

        Returns:
            Whatever ``work`` returns.

        Raises:
            GraphStoreConstraintViolationError: A statement violated a
                uniqueness constraint.
        """
        with self._tracer.start_as_current_span(
            "agrag.graphdb.transaction", kind=SpanKind.INTERNAL
        ):
            await self._ensure_base_schema()
            async with self._transaction_guard.hold():
                return await work(_FalkorDBTransaction(self))

    def shortest_path_distance_query(self) -> str:
        """Build the path-distance query within a bounded number of hops.

        FalkorDB's ``shortestPath`` cannot skip rows that belong to an
        in-flight job, so the query takes the shortest committed path among the
        paths of up to ``MAX_PATH_HOPS`` relationships.
        """
        return shortest_path_distance_query(MAX_PATH_HOPS)

    def vector_value(self, expression: str) -> str:
        """Wrap a float-list expression so FalkorDB stores it as a vector.

        A null expression stays null, so a missing embedding is not an error.
        """
        return f"CASE WHEN {expression} IS NULL THEN null ELSE vecf32({expression}) END"

    def node_write_extra_set(self) -> str:
        """Return the clauses that store vectors and search copies on upsert."""
        vectors = " ".join(
            f"SET n.{name} = CASE WHEN record.properties.{name} IS NULL "
            f"THEN n.{name} ELSE vecf32(record.properties.{name}) END"
            for name in sorted(self._vector_properties)
        )
        copies = self.fulltext_copy_set(
            "n", "record.properties", self._fulltext_properties
        )
        return f"{vectors} {copies}".strip()

    def fulltext_copy_set(
        self, alias: str, source: str, properties: Iterable[str]
    ) -> str:
        """Return ``SET`` clauses that keep the search copies of text properties.

        Args:
            alias: The Cypher variable of the node being written.
            source: A Cypher map expression that holds the written properties.
            properties: The text properties that have a full-text index.

        Returns:
            The clauses, or an empty string when there is nothing to copy.
        """
        clauses = []
        for name in sorted(properties):
            safe = validate_identifier_syntax(name)
            value = f"{source}.{safe}"
            copy = f"{alias}.{_SEARCH_COPY_PREFIX}{safe}"
            flat = f"replace(replace(toString({value}), '\n', ' '), '\r', ' ')"
            clauses.append(
                f"SET {copy} = CASE WHEN NOT '{safe}' IN keys({source}) THEN {copy} "
                f"WHEN {value} IS NULL THEN null ELSE {flat} END"
            )
        return " ".join(clauses)

    @staticmethod
    def _is_record_specific_error(exc: Exception) -> bool:
        """Return whether a FalkorDB error can be caused by one record."""
        if isinstance(exc, GraphStoreConstraintViolationError):
            return True
        return any(message in str(exc) for message in _RECORD_SPECIFIC_MESSAGES)

    @staticmethod
    def _is_missing_index_error(exc: Exception) -> bool:
        """Return whether a vector search failed because the index is absent."""
        return "Invalid arguments for procedure 'db.idx.vector.queryNodes'" in str(exc)

    async def _read_schema(
        self,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Return the raw index rows and constraint rows of the graph."""
        indexes = await self.execute_read("CALL db.indexes()")
        constraints = await self.execute_read("CALL db.constraints()")
        return indexes, constraints

    async def _apply_schema(self, objects: Sequence[_SchemaObject]) -> None:
        """Create the missing indexes and constraints, then wait until usable.

        A uniqueness constraint needs an exact-match index on each of its
        properties first and is built in the background, so the constraints are
        polled until they are ready.

        Raises:
            GraphStoreError: A constraint was not ready in time.
        """
        indexes, constraints = await self._read_schema()
        indexed = {
            (row["entitytype"] == "RELATIONSHIP", row["label"], prop)
            for row in indexes
            for prop, kinds in _index_kinds(row).items()
            if _RANGE in kinds
        }
        constrained = {
            (
                row["entitytype"] == "RELATIONSHIP",
                row["label"],
                tuple(sorted(row["properties"])),
            )
            for row in constraints
        }
        wanted: list[tuple[bool, str, tuple[str, ...]]] = []
        for obj in objects:
            for prop in obj.properties:
                index_key = (obj.relationship, obj.target, prop)
                if index_key not in indexed:
                    await self._create_index(obj, prop)
                    indexed.add(index_key)
            if not obj.unique:
                continue
            key = (obj.relationship, obj.target, tuple(sorted(obj.properties)))
            if key not in constrained:
                await self._create_constraint(obj)
                constrained.add(key)
            wanted.append(key)
        if wanted:
            await self._wait_for_constraints(wanted)

    async def _create_index(self, obj: _SchemaObject, prop: str) -> None:
        """Create one exact-match index, ignoring one that already exists."""
        target = validate_identifier_syntax(obj.target)
        safe_prop = validate_identifier_syntax(prop)
        pattern = (
            f"()-[e:{target}]-() ON (e.{safe_prop})"
            if obj.relationship
            else f"(n:{target}) ON (n.{safe_prop})"
        )
        try:
            await self.execute_write(f"CREATE INDEX FOR {pattern}")
        except Exception as exc:
            if "already indexed" not in str(exc):
                raise

    async def _create_constraint(self, obj: _SchemaObject) -> None:
        """Create one uniqueness constraint, ignoring one that already exists."""
        await self._ensure_client()
        kind = "RELATIONSHIP" if obj.relationship else "NODE"
        try:
            await self._client.connection.execute_command(
                "GRAPH.CONSTRAINT",
                "CREATE",
                self._settings.graph,
                "UNIQUE",
                kind,
                validate_identifier_syntax(obj.target),
                "PROPERTIES",
                len(obj.properties),
                *(validate_identifier_syntax(prop) for prop in obj.properties),
            )
        except Exception as exc:
            if "already exists" not in str(exc):
                raise

    async def _wait_for_constraints(
        self, wanted: Sequence[tuple[bool, str, tuple[str, ...]]]
    ) -> None:
        """Poll until every wanted uniqueness constraint is operational."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _SCHEMA_TIMEOUT_SECONDS
        pending = set(wanted)
        while True:
            rows = await self.execute_read("CALL db.constraints()")
            pending -= {
                (
                    row["entitytype"] == "RELATIONSHIP",
                    row["label"],
                    tuple(sorted(row["properties"])),
                )
                for row in rows
                if row["status"] == "OPERATIONAL"
            }
            if not pending:
                return
            if loop.time() >= deadline:
                raise GraphStoreError(
                    f"FalkorDB constraints were not ready in time: {sorted(pending)}"
                )
            await asyncio.sleep(_SCHEMA_POLL_SECONDS)

    async def _ensure_once(self, key: str, objects: Sequence[_SchemaObject]) -> None:
        """Apply a fixed group of schema objects once per store instance."""
        if key in self._schema_ready:
            return
        async with self._schema_lock:
            if key in self._schema_ready:
                return
            await self._apply_schema(objects)
            self._schema_ready.add(key)

    async def _ensure_identity_constraint(self) -> None:
        """Make node ids unique across every node label, once."""
        await self._ensure_once(
            "identity", [_SchemaObject(NODE_IDENTITY_LABEL, ("id",), unique=True)]
        )

    async def _ensure_relation_constraint(self, rel_type: str) -> None:
        """Make relationship ids unique within one type, once."""
        await self._ensure_once(
            f"relation:{rel_type}",
            [
                _SchemaObject(rel_type, ("id",), relationship=True, unique=True),
                _SchemaObject(rel_type, (PENDING_JOB_ID_PROPERTY,), relationship=True),
            ],
        )

    async def _ensure_candidate_schema(self) -> None:
        """Create the candidate constraints and indexes, once."""
        await self._ensure_once(
            "candidate",
            [
                _SchemaObject(CANDIDATE_LABEL, ("id",), unique=True),
                _SchemaObject(CANDIDATE_LABEL, ("key",)),
                _SchemaObject(CANDIDATE_LABEL, ("state",)),
            ],
        )

    async def _ensure_base_schema(self) -> None:
        """Create the fixed constraints and indexes every write path relies on."""
        await self._ensure_identity_constraint()
        await self._ensure_once(
            "merge_alias",
            [_SchemaObject(MERGE_ALIAS_LABEL, ("merge_key",), unique=True)],
        )
        await self._ensure_once(
            "cutover_job",
            [
                _SchemaObject(CUTOVER_JOB_LABEL, ("document_key",), unique=True),
                _SchemaObject(CUTOVER_JOB_LABEL, ("status",)),
            ],
        )
        await self._ensure_once(
            "pending_tags",
            [
                _SchemaObject(label, (PENDING_JOB_ID_PROPERTY,))
                for label in PENDING_TAGGED_NODE_LABELS
            ],
        )
        await self._ensure_candidate_schema()

    async def setup_constraints(self) -> None:
        """Create ``id`` and ``merge_key`` uniqueness constraints per label.

        Covers every label and relationship type written through this
        instance or already in the database, plus the fixed constraints and
        indexes the write paths rely on. Constraints are built in the
        background, so this returns once each one is operational.
        """
        await self._ensure_base_schema()
        objects: list[_SchemaObject] = []
        for label in sorted(await self._all_labels()):
            objects.append(_SchemaObject(label, ("id",), unique=True))
            objects.append(_SchemaObject(label, ("merge_key",), unique=True))
        for rel_type in sorted(await self._all_relation_types()):
            objects.append(
                _SchemaObject(rel_type, ("id",), relationship=True, unique=True)
            )
            objects.append(
                _SchemaObject(rel_type, (PENDING_JOB_ID_PROPERTY,), relationship=True)
            )
        await self._apply_schema(objects)
        self._schema_ready.update(f"relation:{t}" for t in self._known_relation_types)

    async def upsert_nodes(
        self,
        label: str,
        nodes: Sequence[NodeRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
        deferred: DeferredWrites | None = None,
    ) -> UpsertResult:
        """Write or merge nodes, refusing an embedding of the wrong length.

        FalkorDB accepts a vector of any length into a vector index without an
        error and then never returns it, so a record whose embedding does not
        match the index dimension is reported as a failure instead.
        """
        accepted: list[NodeRecord] = []
        rejected: list[UpsertFailure] = []
        for node in nodes:
            problem = self._embedding_problem(node)
            if problem is None:
                accepted.append(node)
            else:
                rejected.append(
                    UpsertFailure(
                        id=str(node.id),
                        error_type="EmbeddingDimensionMismatchError",
                        error_message=problem,
                    )
                )
        outcome = await super().upsert_nodes(
            label,
            accepted,
            batch_size=batch_size,
            pending_job_id=pending_job_id,
            deferred=deferred,
        )
        outcome.failures.extend(rejected)
        return outcome

    def _embedding_problem(self, node: NodeRecord) -> str | None:
        """Describe an embedding whose length differs from its index, if any."""
        for name in self._vector_properties:
            vector = node.properties.get(name)
            if not isinstance(vector, (list, tuple)):
                continue
            for label in node.labels:
                expected = self._vector_dimensions.get((label, name))
                if expected is not None and len(vector) != expected:
                    return (
                        f"{name} has {len(vector)} values, the {label} index "
                        f"holds {expected}"
                    )
        return None

    async def ensure_unique_constraint(
        self, *, label: str, properties: Sequence[str]
    ) -> None:
        """Make a property combination unique across the nodes of a label."""
        if not properties:
            raise ValueError("a uniqueness constraint needs at least one property")
        safe_label = validate_identifier_syntax(label)
        safe_properties = tuple(validate_identifier_syntax(prop) for prop in properties)
        await self._apply_schema(
            [_SchemaObject(safe_label, safe_properties, unique=True)]
        )

    async def setup_indexes(self) -> None:
        """Set up indexes now provided by the store's uniqueness constraints.

        Kept as a no-op for callers that provision constraints and indexes in
        separate steps: ``setup_constraints`` creates the exact-match indexes
        its constraints need.
        """

    async def list_indexes(self, *, timeout: float | None = None) -> list[IndexInfo]:
        """List every index in the database with its readiness."""
        rows = await self.execute_read("CALL db.indexes()", timeout=timeout)
        found: list[IndexInfo] = []
        for row in rows:
            label = row["label"]
            state = (
                INDEX_STATE_ONLINE if row["status"] == "OPERATIONAL" else row["status"]
            )
            percent = 100.0 if state == INDEX_STATE_ONLINE else None
            by_kind: dict[str, list[str]] = {}
            for prop, kinds in _index_kinds(row).items():
                for kind in kinds:
                    by_kind.setdefault(kind, []).append(prop)
            for prop in by_kind.get(_VECTOR, []):
                options = (row["options"] or {}).get(prop, {})
                found.append(
                    IndexInfo(
                        name=vector_index_name(label, prop),
                        state=state,
                        population_percent=percent,
                        type=_VECTOR,
                        labels=[label],
                        properties=[prop],
                        dimensions=options.get("dimension"),
                    )
                )
            if by_kind.get(_FULLTEXT):
                props = [
                    prop.removeprefix(_SEARCH_COPY_PREFIX)
                    for prop in by_kind[_FULLTEXT]
                ]
                found.append(
                    IndexInfo(
                        name=fulltext_index_name(label, props),
                        state=state,
                        population_percent=percent,
                        type=_FULLTEXT,
                        labels=[label],
                        properties=props,
                    )
                )
            for prop in by_kind.get(_RANGE, []):
                found.append(
                    IndexInfo(
                        name=f"range_{label}_{prop}",
                        state=state,
                        population_percent=percent,
                        type=_RANGE,
                        labels=[label],
                        properties=[prop],
                    )
                )
        return found

    async def ensure_vector_index(
        self, *, label: str, vector_property: str, dimensions: int, distance: Distance
    ) -> None:
        """Create a native vector index if it does not exist.

        Raises:
            EmbeddingDimensionMismatchError: The index exists with a different
                dimension.
            ValueError: ``distance`` is not supported, or a name is unsafe.
        """
        validate_identifier(label)
        validate_identifier(vector_property)
        similarity = _SIMILARITY.get(distance)
        if similarity is None:
            raise ValueError(
                f"FalkorDB vector indexes support cosine and euclidean, not {distance}"
            )
        self._known_labels.add(label)
        self._vector_properties.add(vector_property)
        name = vector_index_name(label, vector_property)
        existing = next(
            (index for index in await self.list_indexes() if index.name == name), None
        )
        if existing is None:
            try:
                await self.execute_write(
                    f"CREATE VECTOR INDEX FOR (n:{label}) ON (n.{vector_property}) "
                    f"OPTIONS {{dimension: {int(dimensions)}, "
                    f"similarityFunction: '{similarity}'}}"
                )
            except Exception as exc:
                if "already indexed" not in str(exc):
                    raise
            existing = next(
                (index for index in await self.list_indexes() if index.name == name),
                None,
            )
        self._vector_similarity[(label, vector_property)] = similarity
        self._vector_dimensions[(label, vector_property)] = dimensions
        if existing is not None and existing.dimensions != dimensions:
            raise EmbeddingDimensionMismatchError(
                expected=existing.dimensions or 0, actual=dimensions
            )

    async def ensure_fulltext_index(
        self, *, label: str, properties: Sequence[str]
    ) -> None:
        """Create a full-text index over node properties if it does not exist."""
        if not properties:
            raise ValueError("a full-text index needs at least one property")
        validate_identifier(label)
        safe_properties = [validate_identifier(prop) for prop in properties]
        self._known_labels.add(label)
        self._fulltext_properties.update(safe_properties)
        indexed = {
            prop
            for index in await self.list_indexes()
            if index.type == _FULLTEXT and index.labels == [label]
            for prop in index.properties
        }
        for prop in safe_properties:
            if prop in indexed:
                continue
            try:
                await self.execute_write(
                    f"CREATE FULLTEXT INDEX FOR (n:{label}) "
                    f"ON (n.{_SEARCH_COPY_PREFIX}{prop})"
                )
            except Exception as exc:
                if "already indexed" not in str(exc):
                    raise

    async def fulltext_search_call(
        self, *, label: str, properties: Sequence[str]
    ) -> SearchCall:
        """Build the Cypher fragment that searches a full-text index.

        FalkorDB scores a match with TF-IDF, which is 0 for a word every
        document holds. One is added so that a match always scores above 0.
        """
        safe_label = validate_identifier(label)
        for prop in properties:
            validate_identifier(prop)
        return SearchCall(
            f"CALL db.idx.fulltext.queryNodes('{safe_label}', $fulltext_terms) "
            "YIELD node, score WITH node, score + 1.0 AS score "
            "ORDER BY score DESC LIMIT $k"
        )

    async def vector_search_call(
        self, *, label: str, vector_property: str
    ) -> SearchCall:
        """Build the Cypher fragment that searches a vector index.

        FalkorDB scores a match by distance, lowest first. The fragment turns
        that into the score Neo4j reports: cosine ``1 - distance / 2``,
        euclidean ``1 / (1 + distance ^ 2)``.
        """
        safe_label = validate_identifier(label)
        safe_property = validate_identifier(vector_property)
        similarity = await self._similarity(safe_label, safe_property)
        score = (
            "1.0 - score / 2.0"
            if similarity == "cosine"
            else "1.0 / (1.0 + score * score)"
        )
        return SearchCall(
            f"CALL db.idx.vector.queryNodes('{safe_label}', '{safe_property}', $k, "
            f"vecf32($vector)) YIELD node, score WITH node, {score} AS score"
        )

    async def _similarity(self, label: str, vector_property: str) -> str:
        """Return the similarity function of a vector index, cosine if unknown."""
        known = self._vector_similarity.get((label, vector_property))
        if known is not None:
            return known
        rows = await self.execute_read("CALL db.indexes()")
        for row in rows:
            options = (row["options"] or {}).get(vector_property)
            if row["label"] == label and options and "similarityFunction" in options:
                known = str(options["similarityFunction"]).lower()
                self._vector_similarity[(label, vector_property)] = known
                return known
        return "cosine"


def _graph_module_version(modules: Any) -> int | None:
    """Read the FalkorDB graph module version from a ``MODULE LIST`` reply."""
    for entry in modules or []:
        fields = _module_fields(entry)
        if fields.get("name") == "graph":
            version = fields.get("ver")
            return int(version) if version is not None else None
    return None


def _module_fields(entry: Any) -> dict[str, Any]:
    """Turn one ``MODULE LIST`` entry into a dict, whatever shape redis gives."""
    if isinstance(entry, Mapping):
        return {_text(key): value for key, value in entry.items()}
    items = list(entry)
    return {_text(items[i]): items[i + 1] for i in range(0, len(items) - 1, 2)}


def _text(value: Any) -> str:
    """Decode a redis reply value to text."""
    return value.decode() if isinstance(value, bytes) else str(value)


def _is_constraint_violation(exc: Exception) -> bool:
    """Return whether a FalkorDB error reports a uniqueness violation."""
    return re.search(r"unique constraint violation", str(exc)) is not None
