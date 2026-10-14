"""Fixtures for the evidence integration tests.

Each test gets a graph with the authored corpus under keys that carry a
per-test run id, so tests can share one database. Teardown deletes only the
nodes under those keys.
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from uuid import uuid4

import pytest

from agrag.chunking import Chunker
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.graph import Graph
from tests.integration.evidence._corpus import (
    HARBOR_TEXT,
    KEEP_TEXT,
    VIBER_TEXT,
    BagOfWordsEmbedder,
    NoEntityExtractor,
    make_document,
)


# Small chunks keep the authored documents to several chunks each.
_CHUNK_SIZE = 60


@dataclass
class EvidenceEnv:
    """A graph loaded with the authored corpus for one test.

    Attributes:
        run: The per-test id that every document key carries.
        store: The connected graph store, shared with the test.
        graph: The graph that wrote the corpus.
    """

    run: str
    store: GraphStore
    graph: Graph

    def key(self, name: str) -> str:
        """Return the document key for a short document name."""
        return f"evidence://{self.run}/{name}"

    @property
    def keep(self) -> str:
        """Return the key of the Keep privacy notice."""
        return self.key("keep")

    @property
    def viber(self) -> str:
        """Return the key of the Viber distractor notice."""
        return self.key("viber")

    @property
    def harbor(self) -> str:
        """Return the key of the long lighthouse log."""
        return self.key("harbor")


async def _cleanup(env: EvidenceEnv) -> None:
    """Delete the chunks and documents written under this run's keys."""
    prefix = env.key("")
    await env.store.execute_write(
        "MATCH (d:Document) WHERE d.document_key STARTS WITH $prefix "
        "MATCH (d)-[:HAS_PART]->(c:Chunk) DETACH DELETE c",
        {"prefix": prefix},
    )
    await env.store.execute_write(
        "MATCH (d:Document) WHERE d.document_key STARTS WITH $prefix DETACH DELETE d",
        {"prefix": prefix},
    )
    await env.store.execute_write(
        "MATCH (j:CutoverJob) WHERE j.document_key STARTS WITH $prefix DETACH DELETE j",
        {"prefix": prefix},
    )


@pytest.fixture
async def evidence_env() -> AsyncGenerator[EvidenceEnv, None]:
    """Open a graph, add the authored corpus, and wait for the indexes."""
    run = uuid4().hex[:8]
    schema = GraphSchema(name="evidence", version="1", entities=[], relations=[])
    store = build_graph_store("neo4j")
    graph = await Graph.open(
        schema=schema,
        graph_store=store,
        embedder=BagOfWordsEmbedder(),
        extractor=NoEntityExtractor(),
        chunker=Chunker(size=_CHUNK_SIZE),
    )
    env = EvidenceEnv(run=run, store=store, graph=graph)
    try:
        await store.execute_read("CALL db.awaitIndexes(60)")
        await graph.add(
            documents=[
                make_document(env.keep, KEEP_TEXT),
                make_document(env.viber, VIBER_TEXT),
                make_document(env.harbor, HARBOR_TEXT),
            ]
        )
        yield env
    finally:
        try:
            await _cleanup(env)
        finally:
            await store.close()
