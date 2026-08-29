"""Graph storage backends and the build shortcut."""

from typing import Callable, Literal

from agrag.graphdb.base import GraphStore
from agrag.graphdb.errors import GraphStoreError, GraphStoreMissingExtraError
from agrag.graphdb.neo4j import Neo4jGraphStore
from agrag.graphdb.settings import Neo4jSettings


def _build_neo4j() -> GraphStore:
    """Build a Neo4j graph store with default settings."""
    return Neo4jGraphStore(settings=Neo4jSettings())


_GRAPH_STORE_FACTORIES: dict[str, Callable[[], GraphStore]] = {
    "neo4j": _build_neo4j,
}

GraphStoreName = Literal["neo4j"]


def build_graph_store(value: GraphStoreName | GraphStore) -> GraphStore:
    """Build a graph store from a backend name, or return one unchanged.

    Args:
        value: ``"neo4j"``, or an already-constructed ``GraphStore``.

    Returns:
        A ready-to-use graph store.
    """
    if isinstance(value, GraphStore):
        return value
    return _GRAPH_STORE_FACTORIES[value]()


__all__ = [
    "GraphStore",
    "GraphStoreError",
    "GraphStoreMissingExtraError",
    "GraphStoreName",
    "Neo4jGraphStore",
    "Neo4jSettings",
    "build_graph_store",
]
