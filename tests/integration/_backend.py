"""Builds the graph store that integration tests run against.

``AGRAG_TEST_BACKENDS`` names the backend for the whole run: ``neo4j`` (the
default) or ``falkordb``. Tests that depend on Neo4j-only behavior carry the
``neo4j_only`` marker and are skipped on any other backend.
"""

import asyncio
import os
from uuid import uuid4

from opentelemetry.trace import Tracer

from agrag.common.data_models.index_record import INDEX_STATE_ONLINE
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.graphdb.falkordb import FalkorDBGraphStore
from agrag.graphdb.settings import FalkorDBSettings


# One graph per test process, so stores built in the same run see the same data,
# as Neo4j stores do, while parallel workers stay apart.
_FALKORDB_GRAPH = f"agrag_test_{uuid4().hex[:12]}"


def selected_backend() -> str:
    """Return the backend name this test run targets."""
    return os.environ.get("AGRAG_TEST_BACKENDS", "neo4j").strip() or "neo4j"


def server_environment() -> dict[str, str]:
    """Return the variables that point a server subprocess at the test graph."""
    if selected_backend() == "falkordb":
        return {"MCP_GRAPH_STORE": "falkordb", "FALKORDB_GRAPH": _FALKORDB_GRAPH}
    return {}


def build_test_store(*, tracer: Tracer | None = None) -> GraphStore:
    """Build a store for the selected backend.

    A FalkorDB store uses a graph that belongs to this test process, so xdist
    workers never share data. A Neo4j store uses the configured database. In both
    cases tests share the data by giving every label and relationship type a
    unique suffix.

    Args:
        tracer: Opens the spans the store produces.

    Returns:
        A store that is not connected yet.
    """
    if selected_backend() == "falkordb":
        base = FalkorDBSettings()
        return FalkorDBGraphStore(
            settings=base.model_copy(update={"graph": _FALKORDB_GRAPH}), tracer=tracer
        )
    return build_graph_store("neo4j", tracer=tracer)


async def await_indexes(store: GraphStore, timeout: float = 60.0) -> None:
    """Wait until every index in the database is online.

    Args:
        store: A connected graph store.
        timeout: Seconds to wait before giving up.

    Raises:
        TimeoutError: An index was still building when the time ran out.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    while any(
        index.state != INDEX_STATE_ONLINE for index in await store.list_indexes()
    ):
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError("indexes did not come online")
        await asyncio.sleep(0.1)
