"""Neo4j graph-store backend."""

import asyncio
from collections import defaultdict
from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Any
from uuid import UUID

from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.vector_record import Distance, VectorHit
from agrag.common.validation import require_positive_batch_size
from agrag.cypher.entities import (
    NODE_IDENTITY_LABEL,
    is_safe_identifier,
    upsert_node_query,
    validate_identifier,
)
from agrag.cypher.relations import upsert_relation_query
from agrag.cypher.schema import (
    node_id_constraint_query,
    plain_index_query,
    relation_id_constraint_query,
    vector_index_name,
    vector_index_query,
    vector_search_query,
)
from agrag.graphdb.base import GraphStore
from agrag.graphdb.errors import GraphStoreMissingExtraError
from agrag.graphdb.serialize import node_params, relation_params
from agrag.graphdb.settings import Neo4jSettings


if TYPE_CHECKING:
    from neo4j import AsyncDriver


# db.index.vector.queryNodes selects its top-k candidates before a WHERE
# filter runs, so a filtered call can return fewer than the requested limit
# even when enough matching nodes exist. Escalate k geometrically and retry
# until enough filtered hits come back or this ceiling is reached, matching
# Neo4j's own practical limit on a single vector query's k.
_VECTOR_SEARCH_OVERFETCH_MULTIPLIER = 4
_VECTOR_SEARCH_MAX_K = 1000


class Neo4jGraphStore(GraphStore):
    """A ``GraphStore`` backed by Neo4j, using native vector indexes.

    The driver connects lazily on first use, so constructing the store does not
    open a network connection. ``execute_read``/``execute_write`` wrap the
    driver's managed transactions with no added retry loop, per ADR 0027.
    """

    def __init__(
        self,
        *,
        settings: Neo4jSettings | None = None,
        driver: "AsyncDriver | None" = None,
    ) -> None:
        """Build the store.

        Args:
            settings: Neo4j connection settings. Defaults to ``Neo4jSettings()``.
            driver: A pre-built ``AsyncDriver``, for tests. When set,
                ``__init__`` imports nothing and the store calls this object
                directly instead of building one.
        """
        self._settings = settings or Neo4jSettings()
        self._driver: Any = driver
        self._driver_lock = asyncio.Lock()
        self._known_labels: set[str] = set()
        self._known_relation_types: set[str] = set()
        self._identity_constraint_ready = False
        self._identity_constraint_lock = asyncio.Lock()
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
            try:
                # Lazy import: a clean install must raise
                # GraphStoreMissingExtraError, not ImportError, when neo4j is
                # absent.
                from neo4j import AsyncGraphDatabase  # noqa: PLC0415
            except ImportError as exc:
                raise GraphStoreMissingExtraError("neo4j") from exc
            self._driver = AsyncGraphDatabase.driver(
                self._settings.uri,
                auth=(
                    self._settings.username,
                    self._settings.password.get_secret_value(),
                ),
                max_connection_lifetime=self._settings.max_connection_lifetime,
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
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a read transaction and return its rows."""
        async with self.session() as s:
            return await s.execute_read(self._run, query, parameters or {})

    async def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a write transaction and return its rows."""
        async with self.session() as s:
            return await s.execute_write(self._run, query, parameters or {})

    @staticmethod
    async def _run(
        tx: Any, query: str, parameters: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        """Run a single query inside a managed transaction and read its rows."""
        result = await tx.run(query, parameters)
        return await result.data()

    async def setup_constraints(self) -> None:
        """Create a uniqueness constraint on ``id`` for every known label.

        "Known" means written by this instance or already present in the
        database, so a fresh store can set up constraints for an existing
        database without first rewriting every record. Also creates the
        global uniqueness constraint on ``NODE_IDENTITY_LABEL`` that
        ``upsert_node_query``'s ``MERGE`` relies on to resolve a node by id
        regardless of its other, mutable labels, and a per-type uniqueness
        constraint on ``id`` for every known relationship type, which backs
        the stale-relationship cleanup ``upsert_relation_query`` performs on
        endpoint changes.
        """
        await self._ensure_identity_constraint()
        for label in await self._all_labels():
            await self.execute_write(node_id_constraint_query(label))
        for rel_type in await self._all_relation_types():
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
            self._relation_type_constraints_ready.add(rel_type)

    async def register_labels(self, labels: Sequence[str]) -> None:
        """Add labels to this instance's known-label set.

        Args:
            labels: The labels to register. Each must be a safe Cypher
                identifier.

        Raises:
            ValueError: Any label is not a safe identifier.
        """
        for label in labels:
            validate_identifier(label)
        self._known_labels.update(labels)

    async def register_relation_types(self, types: Sequence[str]) -> None:
        """Add types to this instance's known-relation-type set.

        Args:
            types: The relationship types to register. Each must be a safe
                Cypher identifier.

        Raises:
            ValueError: Any type is not a safe identifier.
        """
        for rel_type in types:
            validate_identifier(rel_type)
        self._known_relation_types.update(types)

    async def setup_indexes(self) -> None:
        """Create a range index on ``id`` for every known label.

        "Known" means written by this instance or already present in the
        database, so a fresh store can set up indexes for an existing
        database without first rewriting every record.
        """
        for label in await self._all_labels():
            await self.execute_write(plain_index_query(label))
            try:
                from agrag.cypher import entities as _cypher_entities  # noqa: PLC0415

                merge_key_fn = getattr(_cypher_entities, "merge_key_index_query", None)
                if merge_key_fn is not None:
                    await self.execute_write(merge_key_fn(label))
            except ImportError:
                pass

    async def _all_labels(self) -> set[str]:
        """Return every node label this instance knows about.

        Combines labels written through this instance with every label
        already present in the database, so setup does not depend on this
        instance having written the data itself. A live label outside this
        store's stricter identifier subset (Neo4j itself allows names our
        Cypher builders cannot safely interpolate unquoted, such as ones with
        spaces or hyphens) is skipped rather than raised, so one such name
        left over from other tooling cannot block every other constraint.

        Returns:
            The label names, excluding the internal identity anchor.
        """
        rows = await self.execute_read("CALL db.labels() YIELD label RETURN label")
        live = {
            row["label"]
            for row in rows
            if row["label"] != NODE_IDENTITY_LABEL and is_safe_identifier(row["label"])
        }
        return self._known_labels | live

    async def _all_relation_types(self) -> set[str]:
        """Return every relationship type this instance knows about.

        Combines types written through this instance with every type already
        present in the database, so setup does not depend on this instance
        having written the data itself. A live type outside this store's
        stricter identifier subset is skipped rather than raised, so one such
        name left over from other tooling cannot block every other
        constraint.

        Returns:
            The relationship type names.
        """
        rows = await self.execute_read(
            "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
        )
        live = {
            row["relationshipType"]
            for row in rows
            if is_safe_identifier(row["relationshipType"])
        }
        return self._known_relation_types | live

    async def upsert_nodes(
        self,
        label: str,
        nodes: Sequence[NodeRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Write or merge nodes, honoring each record's full label set.

        ``label`` names the batch for constraint/index bookkeeping, matching
        every other tracked label; the labels actually written to a node come
        from ``NodeRecord.labels``, which may name more than one label (for
        example a node that is both ``Chunk`` and ``Entity``). Records with
        different label sets are grouped and written with separate ``MERGE``
        queries, since Cypher requires labels to be literal in the query text
        rather than a runtime parameter, so ``batch_size`` chunks apply within
        each group rather than across the whole call.

        Raises:
            ValueError: ``batch_size`` is not positive.
        """
        require_positive_batch_size(batch_size)
        validate_identifier(label)
        await self._ensure_identity_constraint()
        self._known_labels.add(label)
        groups: dict[tuple[str, ...], list[NodeRecord]] = defaultdict(list)
        for node in nodes:
            labels = tuple(sorted(set(node.labels)))
            for node_label in labels:
                validate_identifier(node_label)
            self._known_labels.update(labels)
            groups[labels].append(node)
        for labels, group_nodes in groups.items():
            query = upsert_node_query(labels)
            await self._batch_write(
                query, [node_params(n) for n in group_nodes], batch_size
            )

    async def upsert_relations(
        self,
        relations: Sequence[RelationRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Write or merge relationships between existing nodes.

        Relationship identity is each record's ``id``, not its endpoints: see
        ``upsert_relation_query`` for how endpoint changes and same-id
        parallel relationships are handled.

        Raises:
            ValueError: ``batch_size`` is not positive.
        """
        require_positive_batch_size(batch_size)
        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for rel in relations:
            validate_identifier(rel.type)
            by_type[rel.type].append(relation_params(rel))
        for rel_type, params in by_type.items():
            await self._ensure_relation_constraint(rel_type)
            self._known_relation_types.add(rel_type)
            query = upsert_relation_query(rel_type)
            await self._batch_write(query, params, batch_size)

    async def ensure_vector_index(
        self, *, label: str, vector_property: str, dimensions: int, distance: Distance
    ) -> None:
        """Create a native vector index if it does not exist."""
        validate_identifier(label)
        validate_identifier(vector_property)
        self._known_labels.add(label)
        await self.execute_write(
            vector_index_query(label, vector_property, dimensions, distance)
        )

    async def vector_search(
        self,
        *,
        label: str,
        vector_property: str,
        query_vector: Sequence[float],
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        """Search nodes by dense vector using the native vector index.

        When ``filters`` is set, Neo4j's vector procedure applies the filter
        only after selecting its top ``k`` candidates, so a plain ``k=limit``
        call can return fewer matches than actually exist. This escalates
        ``k`` and retries until ``limit`` filtered hits come back or the
        escalation reaches ``_VECTOR_SEARCH_MAX_K``.

        Raises:
            ValueError: ``limit`` is not positive. A non-positive value is
                not a meaningful request and would send that same
                non-positive ``k`` to Neo4j's native vector procedure, which
                requires a positive top-k.
        """
        if limit <= 0:
            raise ValueError(f"limit must be positive, got {limit}")
        validate_identifier(label)
        validate_identifier(vector_property)
        index_name = vector_index_name(label, vector_property)
        query, filter_params = vector_search_query(index_name, filters)
        k = limit
        rows: list[dict[str, Any]] = []
        while True:
            params: dict[str, Any] = {
                **filter_params,
                "index": index_name,
                "k": k,
                "vector": list(query_vector),
            }
            rows = await self.execute_read(query, params)
            if not filters or len(rows) >= limit or k >= _VECTOR_SEARCH_MAX_K:
                break
            k = min(k * _VECTOR_SEARCH_OVERFETCH_MULTIPLIER, _VECTOR_SEARCH_MAX_K)
        hits: list[VectorHit] = []
        for row in rows[:limit]:
            node = row["node"]
            node_props = dict(node)
            node_props.pop(vector_property, None)
            node_props.pop("id", None)
            hits.append(
                VectorHit(
                    id=UUID(node["id"]),
                    score=float(row["score"]),
                    payload=node_props,
                )
            )
        return hits

    async def _batch_write(
        self, query: str, records: Sequence[dict[str, Any]], batch_size: int
    ) -> None:
        """Run ``query`` once per ``batch_size`` chunk of ``records``."""
        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            await self.execute_write(query, {"records": batch})
