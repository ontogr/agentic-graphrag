"""Neo4j graph-store backend."""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Any
from uuid import UUID

from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.vector_record import Distance, VectorHit
from agrag.cypher.entities import upsert_node_query, validate_identifier
from agrag.cypher.relations import upsert_relation_query
from agrag.cypher.schema import (
    node_id_constraint_query,
    plain_index_query,
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
        self._known_labels: set[str] = set()

    async def _ensure_driver(self) -> "AsyncDriver":
        """Build the Neo4j driver once and cache it.

        Returns:
            The connected driver object.

        Raises:
            GraphStoreMissingExtraError: the neo4j driver is not installed.
        """
        if self._driver is None:
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
        """Create a uniqueness constraint on ``id`` for every tracked label."""
        for label in self._known_labels:
            await self.execute_write(node_id_constraint_query(label))

    async def setup_indexes(self) -> None:
        """Create a range index on ``id`` for every tracked label."""
        for label in self._known_labels:
            await self.execute_write(plain_index_query(label))

    async def upsert_nodes(
        self,
        label: str,
        nodes: Sequence[NodeRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Write or merge nodes of one label."""
        validate_identifier(label)
        self._known_labels.add(label)
        query = upsert_node_query(label)
        await self._batch_write(query, [node_params(n) for n in nodes], batch_size)

    async def upsert_relations(
        self,
        relations: Sequence[RelationRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Write or merge relationships between existing nodes."""
        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for rel in relations:
            validate_identifier(rel.type)
            by_type[rel.type].append(relation_params(rel))
        for rel_type, params in by_type.items():
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
        """Search nodes by dense vector using the native vector index."""
        validate_identifier(label)
        validate_identifier(vector_property)
        index_name = vector_index_name(label, vector_property)
        query, filter_params = vector_search_query(index_name, filters)
        params: dict[str, Any] = {
            **filter_params,
            "index": index_name,
            "k": limit,
            "vector": list(query_vector),
        }
        rows = await self.execute_read(query, params)
        hits: list[VectorHit] = []
        for row in rows:
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
