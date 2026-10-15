"""Shared fixtures for task memory integration tests.

Every test gets its own project ids, so tests share one database without seeing
each other's tasks. Teardown deletes only the Task, Event, Step, Decision,
Support and Request nodes of those projects. Uniqueness constraints are left in
place because other tests use the same labels. The document fixture writes
authored documents under keys with a per-test run id and deletes only those.
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from uuid import uuid4

import pytest

from agrag.chunking import Chunker
from agrag.common.data_models.decision import DECISION_LABEL
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.cypher.schema import fulltext_index_name
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.graph import Graph
from tests.integration.retrieval.evidence._corpus import (
    HARBOR_TEXT,
    KEEP_TEXT,
    BagOfWordsEmbedder,
    NoEntityExtractor,
    make_document,
)


DECISION_TEXT_PROPERTIES = ["conclusion", "rationale"]


async def _delete_project_memory(store: GraphStore, project_id: str) -> None:
    """Delete the task memory nodes that belong to one project.

    Args:
        store: A connected graph store.
        project_id: The project whose nodes are removed.
    """
    params = {"project_id": project_id}
    await store.execute_write(
        "MATCH (d:MemoryDecision {project_id: $project_id}) "
        "OPTIONAL MATCH (d)-[:HAS_SUPPORT]->(s) "
        "DETACH DELETE s, d",
        params,
    )
    await store.execute_write(
        "MATCH (t:MemoryTask {project_id: $project_id}) "
        "OPTIONAL MATCH (t)-[:HAS_EVENT|HAS_STEP]->(child) "
        "DETACH DELETE child, t",
        params,
    )
    await store.execute_write(
        "MATCH (r:MemoryRequest {project_id: $project_id}) DETACH DELETE r", params
    )
    await store.execute_write(
        "MATCH (p:MemoryProject {project_id: $project_id}) DETACH DELETE p", params
    )


async def ready_decision_index(store: GraphStore) -> None:
    """Create the decision full-text index if needed and wait until it is online.

    Args:
        store: A connected graph store.
    """
    await store.ensure_fulltext_index(
        label=DECISION_LABEL, properties=DECISION_TEXT_PROPERTIES
    )
    await store.execute_read("CALL db.awaitIndexes(60)")
    assert fulltext_index_name(DECISION_LABEL, DECISION_TEXT_PROPERTIES)


@pytest.fixture
async def store() -> AsyncGenerator[GraphStore, None]:
    """Open the configured Neo4j store for one test."""
    graph_store = build_graph_store("neo4j")
    async with graph_store:
        yield graph_store


@pytest.fixture
async def project(store: GraphStore) -> AsyncGenerator[str, None]:
    """Yield a project id no other test uses, and delete its nodes afterwards."""
    project_id = f"proj-{uuid4().hex[:8]}"
    try:
        yield project_id
    finally:
        await _delete_project_memory(store, project_id)


@pytest.fixture
async def other_project(store: GraphStore) -> AsyncGenerator[str, None]:
    """Yield a second project id for scope tests, and delete its nodes afterwards."""
    project_id = f"proj-{uuid4().hex[:8]}"
    try:
        yield project_id
    finally:
        await _delete_project_memory(store, project_id)


@dataclass
class DocumentEnv:
    """Authored documents ingested for one test.

    Attributes:
        run: The per-test id that every document key carries.
        store: The connected graph store.
        graph: The graph that wrote the documents.
    """

    run: str
    store: GraphStore
    graph: Graph

    def key(self, name: str) -> str:
        """Return the document key for a short document name."""
        return f"memory://{self.run}/{name}"

    @property
    def keep(self) -> str:
        """Return the key of the privacy notice document."""
        return self.key("keep")

    @property
    def harbor(self) -> str:
        """Return the key of the lighthouse log document."""
        return self.key("harbor")


async def _delete_documents(env: DocumentEnv) -> None:
    """Delete the nodes written under this run's document keys."""
    params = {"prefix": env.key("")}
    await env.store.execute_write(
        "MATCH (d:Document) WHERE d.document_key STARTS WITH $prefix "
        "MATCH (d)-[:HAS_PART]->(c:Chunk) DETACH DELETE c",
        params,
    )
    await env.store.execute_write(
        "MATCH (d:Document) WHERE d.document_key STARTS WITH $prefix "
        "OPTIONAL MATCH (d)-[:HAS_ACTIVATION]->(a) DETACH DELETE a, d",
        params,
    )
    await env.store.execute_write(
        "MATCH (j:CutoverJob) WHERE j.document_key STARTS WITH $prefix DETACH DELETE j",
        params,
    )


@pytest.fixture
async def documents(store: GraphStore) -> AsyncGenerator[DocumentEnv, None]:
    """Ingest two authored documents with fake models and yield them.

    The embedder and extractor are the deterministic fakes of the evidence tests,
    so no model runs. The Chunk vector index in the shared database has four
    dimensions, which only the bag-of-words embedder matches.
    """
    run = uuid4().hex[:8]
    schema = GraphSchema(name="memory", version="1", entities=[], relations=[])
    graph = await Graph.open(
        schema=schema,
        graph_store=store,
        embedder=BagOfWordsEmbedder(),
        extractor=NoEntityExtractor(),
        chunker=Chunker(size=60),
    )
    env = DocumentEnv(run=run, store=store, graph=graph)
    try:
        await store.execute_read("CALL db.awaitIndexes(60)")
        await graph.add(
            documents=[
                make_document(env.keep, KEEP_TEXT),
                make_document(env.harbor, HARBOR_TEXT),
            ]
        )
        yield env
    finally:
        await _delete_documents(env)
