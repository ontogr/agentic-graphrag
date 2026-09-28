"""Graph storage backends and the build shortcut."""

from typing import Callable, Literal

from opentelemetry.trace import Tracer

from agrag.graphdb.base import GraphStore
from agrag.graphdb.errors import GraphStoreError, GraphStoreMissingExtraError
from agrag.graphdb.neo4j import Neo4jGraphStore
from agrag.graphdb.settings import Neo4jSettings


def _build_neo4j(tracer: Tracer | None = None) -> GraphStore:
    """Build a Neo4j graph store with default settings."""
    return Neo4jGraphStore(settings=Neo4jSettings(), tracer=tracer)


_GRAPH_STORE_FACTORIES: dict[str, Callable[..., GraphStore]] = {
    "neo4j": _build_neo4j,
}

GraphStoreName = Literal["neo4j"]


def build_graph_store(
    value: GraphStoreName | GraphStore, *, tracer: Tracer | None = None
) -> GraphStore:
    """Build a graph store from a backend name, or return one unchanged.

    Args:
        value: ``"neo4j"``, or an already-constructed ``GraphStore``.
        tracer: Passed to the newly-built store. Not valid together with an
            already-constructed ``value`` -- that instance's tracer, if any,
            was already fixed at its own construction.

    Returns:
        A ready-to-use graph store.

    Raises:
        ValueError: ``tracer`` is given together with an already-constructed
            ``value``.
    """
    if isinstance(value, GraphStore):
        if tracer is not None:
            raise ValueError(
                "tracer has no effect on an already-constructed GraphStore; "
                "pass it to the store's own constructor instead."
            )
        return value
    return _GRAPH_STORE_FACTORIES[value](tracer=tracer)


__all__ = [
    "GraphStore",
    "GraphStoreError",
    "GraphStoreMissingExtraError",
    "GraphStoreName",
    "Neo4jGraphStore",
    "Neo4jSettings",
    "build_graph_store",
]
