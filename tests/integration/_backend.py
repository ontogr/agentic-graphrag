"""Builds the graph store that integration tests run against.

``AGRAG_TEST_BACKENDS`` names the backend for the whole run: ``neo4j`` (the
default) or ``falkordb``. Tests that depend on Neo4j-only behavior carry the
``neo4j_only`` marker and are skipped on any other backend.
"""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
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


@asynccontextmanager
async def isolated_test_store() -> AsyncIterator[tuple[GraphStore, dict[str, str]]]:
    """Yield an unconnected store whose data no other test shares.

    A FalkorDB store gets its own graph, dropped on exit. Deleted nodes stay in
    the full-text index statistics of a graph, so tests that assert on ranking
    cannot share a graph with tests that delete data. A Neo4j store uses the
    configured database, as ``build_test_store`` does, and the test removes its
    own data.

    Yields:
        The store, and the variables that point a server subprocess at the same
        data.
    """
    if selected_backend() != "falkordb":
        yield build_test_store(), {}
        return
    from redis.asyncio import Redis  # noqa: PLC0415

    settings = FalkorDBSettings()
    graph = f"agrag_test_{uuid4().hex[:12]}"
    store = FalkorDBGraphStore(settings=settings.model_copy(update={"graph": graph}))
    try:
        yield store, {"MCP_GRAPH_STORE": "falkordb", "FALKORDB_GRAPH": graph}
    finally:
        await store.close()
        password = settings.password
        async with Redis.from_url(
            settings.url, password=password.get_secret_value() if password else None
        ) as redis:
            await redis.execute_command("GRAPH.DELETE", graph)


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
