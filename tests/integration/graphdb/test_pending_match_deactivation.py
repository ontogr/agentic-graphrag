"""Deactivating a match ignores pending edges, against real Neo4j.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``).
"""

import importlib.util
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.resolved_entities import deactivate_match_and_rebuild


neo4j_missing = importlib.util.find_spec("neo4j") is None

pytestmark = [
    pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed"),
    pytest.mark.asyncio(loop_scope="module"),
]


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def store() -> AsyncIterator[GraphStore]:
    """Open one connected store for the module."""
    graph_store = build_graph_store("neo4j")
    await graph_store.connect()
    try:
        yield graph_store
    finally:
        await graph_store.close()


async def _create(store: GraphStore, tag: str, query: str, **params: object) -> None:
    """Run one setup write; every node it makes carries ``tag`` as ``probe``."""
    await store.execute_write(query, {"tag": tag, **params})


async def _drop(store: GraphStore, tag: str) -> None:
    """Delete every node one test created, and the derived entities they own."""
    await store.execute_write(
        "MATCH (:_Node {probe: $tag})-[:RESOLVED_AS]->(r:ResolvedEntity) "
        "DETACH DELETE r",
        {"tag": tag},
    )
    await store.execute_write(
        "MATCH (n:_Node {probe: $tag}) DETACH DELETE n", {"tag": tag}
    )


def _schema(label: str) -> GraphSchema:
    """Build the smallest schema that declares the probe entity label."""
    return GraphSchema(
        name="pending-match-deactivation-probe",
        version="1",
        entities=[EntityType(label=label, description="Probe entity.")],
        relations=[],
    )


async def _create_matched_pair(
    store: GraphStore, tag: str, label: str, match: UUID, job: str | None
) -> None:
    """Create two entities joined by one active MATCHES edge.

    Args:
        store: The store the setup write runs against.
        tag: The probe tag stored on every node.
        label: The entity label encoded in each node's ``merge_key``.
        match: The id stored on the MATCHES edge.
        job: The in-flight job id tagging the edge, or None for a committed edge.
    """
    edge_properties = "" if job is None else ", _pending_job_id: $job"
    await _create(
        store,
        tag,
        "CREATE (a:_Node {id: $a, probe: $tag, name: 'a', merge_key: $key_a}) "
        "CREATE (b:_Node {id: $b, probe: $tag, name: 'b', merge_key: $key_b}) "
        "CREATE (a)-[:MATCHES {id: $match, active: true"
        f"{edge_properties}}}]->(b)",
        a=str(uuid4()),
        b=str(uuid4()),
        key_a=f"{label}:a",
        key_b=f"{label}:b",
        match=str(match),
        job=job,
    )


async def _match_active_flag(store: GraphStore, match: UUID) -> object:
    """Read the ``active`` flag of one MATCHES edge."""
    rows = await store.execute_read(
        "MATCH ()-[r:MATCHES {id: $match}]->() RETURN r.active AS active",
        {"match": str(match)},
    )
    assert len(rows) == 1
    return rows[0]["active"]


class TestPendingMatchDeactivation:
    """Deactivating a match only touches committed match edges."""

    @staticmethod
    async def test_deactivate_match_ignores_a_pending_edge(store: GraphStore) -> None:
        """A match an in-flight job wrote cannot be deactivated as committed."""
        tag, job = uuid4().hex, str(uuid4())
        label = f"PendingProbeDeact{tag[:12]}"
        match = uuid4()
        try:
            await _create_matched_pair(store, tag, label, match, job)

            with pytest.raises(ValueError, match="does not exist"):
                await deactivate_match_and_rebuild(
                    match, graph_store=store, schema=_schema(label)
                )

            assert await _match_active_flag(store, match) is True
        finally:
            await _drop(store, tag)

    @staticmethod
    async def test_deactivate_match_still_works_on_a_committed_edge(
        store: GraphStore,
    ) -> None:
        """A committed match is deactivated and the edge is kept."""
        tag = uuid4().hex
        label = f"PendingProbeDeact{tag[:12]}"
        match = uuid4()
        try:
            await _create_matched_pair(store, tag, label, match, None)

            await deactivate_match_and_rebuild(
                match, graph_store=store, schema=_schema(label)
            )

            assert await _match_active_flag(store, match) is False
        finally:
            await _drop(store, tag)
