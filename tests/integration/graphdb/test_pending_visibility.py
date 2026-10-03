"""Pending rows never reach reads that carry no job id, against real Neo4j.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``).
"""

import importlib.util
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio

from agrag.cypher.community_read import hydrate_communities_by_id_query
from agrag.cypher.entities import fetch_all_by_label_query, fetch_entity_neighbors_query
from agrag.cypher.relations import shortest_path_distance_query
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion._document_lifecycle import find_document


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
    """Delete every node one test created."""
    await store.execute_write(
        "MATCH (n:_AgragNode {probe: $tag}) DETACH DELETE n", {"tag": tag}
    )


class TestPendingVisibility:
    """Reads without a job id return committed rows only."""

    async def test_all_by_label_skips_pending_nodes(self, store: GraphStore) -> None:
        """Consolidation never sees an entity an in-flight job wrote."""
        tag, job = uuid4().hex, str(uuid4())
        label = f"PendingProbeAll{tag[:12]}"
        committed, pending = str(uuid4()), str(uuid4())
        try:
            await _create(
                store,
                tag,
                f"CREATE (:_AgragNode:{label} {{id: $a, probe: $tag}}) "
                f"CREATE (:_AgragNode:{label} "
                "{id: $b, probe: $tag, _pending_job_id: $job})",
                a=committed,
                b=pending,
                job=job,
            )

            rows = await store.execute_read(
                fetch_all_by_label_query(label), {"skip": 0, "limit": 100}
            )

            assert {row["n"]["id"] for row in rows} == {committed}
        finally:
            await _drop(store, tag)

    async def test_neighbors_skip_pending_nodes_and_edges(
        self, store: GraphStore
    ) -> None:
        """Resolution context never samples a pending neighbour or edge."""
        tag, job = uuid4().hex, str(uuid4())
        seed, kept, via_pending_edge, pending_node = (str(uuid4()) for _ in range(4))
        try:
            await _create(
                store,
                tag,
                "CREATE (s:_AgragNode {id: $seed, probe: $tag, name: 'seed'}) "
                "CREATE (k:_AgragNode {id: $kept, probe: $tag, name: 'kept'}) "
                "CREATE (e:_AgragNode {id: $edge, probe: $tag, name: 'edge'}) "
                "CREATE (p:_AgragNode "
                "{id: $node, probe: $tag, name: 'node', _pending_job_id: $job}) "
                "CREATE (s)-[:KNOWS]->(k) "
                "CREATE (s)-[:KNOWS {_pending_job_id: $job}]->(e) "
                "CREATE (s)-[:KNOWS]->(p)",
                seed=seed,
                kept=kept,
                edge=via_pending_edge,
                node=pending_node,
                job=job,
            )

            rows = await store.execute_read(
                fetch_entity_neighbors_query(),
                {"ids": [seed], "exclude_types": [], "limit": 10},
            )

            assert [row["neighbor_name"] for row in rows] == ["kept"]
        finally:
            await _drop(store, tag)

    async def test_shortest_path_ignores_pending_shortcuts(
        self, store: GraphStore
    ) -> None:
        """A pending edge cannot shorten a committed distance."""
        tag, job = uuid4().hex, str(uuid4())
        a, b, middle, only_pending = (str(uuid4()) for _ in range(4))
        try:
            await _create(
                store,
                tag,
                "CREATE (a:_AgragNode {id: $a, probe: $tag}) "
                "CREATE (m:_AgragNode {id: $m, probe: $tag}) "
                "CREATE (b:_AgragNode {id: $b, probe: $tag}) "
                "CREATE (c:_AgragNode {id: $c, probe: $tag}) "
                "CREATE (a)-[:KNOWS]->(m)-[:KNOWS]->(b) "
                "CREATE (a)-[:KNOWS {_pending_job_id: $job}]->(b) "
                "CREATE (a)-[:KNOWS {_pending_job_id: $job}]->(c)",
                a=a,
                b=b,
                m=middle,
                c=only_pending,
                job=job,
            )

            shortened = await store.execute_read(
                shortest_path_distance_query(), {"seed_ids": [a], "target_ids": [b]}
            )
            unreachable = await store.execute_read(
                shortest_path_distance_query(),
                {"seed_ids": [a], "target_ids": [only_pending]},
            )

            assert [row["dist"] for row in shortened] == [2]
            assert unreachable == []
        finally:
            await _drop(store, tag)

    async def test_communities_skip_pending_nodes(self, store: GraphStore) -> None:
        """Community hydration never returns an uncommitted community."""
        tag, job = uuid4().hex, str(uuid4())
        committed, pending = str(uuid4()), str(uuid4())
        try:
            await _create(
                store,
                tag,
                "CREATE (:_AgragNode:Community {id: $a, probe: $tag}) "
                "CREATE (:_AgragNode:Community "
                "{id: $b, probe: $tag, _pending_job_id: $job})",
                a=committed,
                b=pending,
                job=job,
            )

            rows = await store.execute_read(
                hydrate_communities_by_id_query(), {"ids": [committed, pending]}
            )

            assert {row["n"]["id"] for row in rows} == {committed}
        finally:
            await _drop(store, tag)

    async def test_document_lookup_skips_pending_chunks(
        self, store: GraphStore
    ) -> None:
        """A version an in-flight job wrote is not read as the current chunker."""
        tag, job = uuid4().hex, str(uuid4())
        key = f"pending-visibility://{tag}"
        try:
            await _create(
                store,
                tag,
                "CREATE (d:_AgragNode:Document {id: $doc, probe: $tag, "
                "document_key: $key, current_content_hash: 'h'}) "
                "CREATE (c:_AgragNode:Chunk {id: $chunk, probe: $tag, "
                "chunker_hash: 'staged', _pending_job_id: $job}) "
                "CREATE (d)-[:PART_OF {_pending_job_id: $job}]->(c)",
                doc=str(uuid4()),
                chunk=str(uuid4()),
                key=key,
                job=job,
            )

            found = await find_document(store, document_key=key)

            assert found is not None
            assert found.current_chunker_hash is None
        finally:
            await _drop(store, tag)

    async def test_document_lookup_skips_pending_documents(
        self, store: GraphStore
    ) -> None:
        """An uncommitted document hash is never read as the current one."""
        tag, job = uuid4().hex, str(uuid4())
        key = f"pending-visibility://{tag}"
        try:
            await _create(
                store,
                tag,
                "CREATE (:_AgragNode:Document {id: $doc, probe: $tag, "
                "document_key: $key, current_content_hash: 'staged', "
                "_pending_job_id: $job})",
                doc=str(uuid4()),
                key=key,
                job=job,
            )

            found = await find_document(store, document_key=key)

            assert found is None
        finally:
            await _drop(store, tag)
