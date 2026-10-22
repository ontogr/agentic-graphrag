"""Integration tests for the content hash that each Chunk node records.

A chunk node stores the content hash of the document version it was cut
from. Superseded chunks keep the hash of the text they came from, so a closed
chunk still says which content it belonged to. The tests run against a real
Neo4j with a fake embedder and a fake extractor. Every key and text carries a
per-run id, so the tests can share a database with other tests.
"""

import hashlib
import importlib.util
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from tests.conftest import FAKE_EMBEDDING_DIMENSIONS
from tests.integration._backend import build_test_store


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _ConstantEmbedder(Embedder):
    """Embedder that returns the same vector for every text."""

    model = "constant"

    async def dimensions(self) -> int:
        """Return the dimension of the shared Chunk vector index."""
        return FAKE_EMBEDDING_DIMENSIONS

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one fixed vector per text."""
        return [[0.25] * FAKE_EMBEDDING_DIMENSIONS for _ in texts]


class _NoEntityExtractor(Extractor):
    """Extractor that finds no entities in any chunk."""

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return an empty extraction result."""
        return ExtractionResult(entities=[], relations=[], extractor_name="fake")


def _sha256(text: str) -> str:
    """Hash ASCII text the way the document lifecycle does."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _document(key: str, text: str) -> Document:
    """Build a prose Document with an explicit stable key."""
    return Document(
        text=text,
        title="content hash",
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=_sha256(text),
        loader_name="inline",
        encoding="utf-8",
        char_count=len(text),
        line_count=text.count("\n") + 1,
    )


@dataclass
class _Env:
    """Everything one test needs, all scoped to one run id."""

    run: str
    store: GraphStore
    graph: Graph

    def key(self, name: str) -> str:
        """Return the document key for a short name."""
        return f"content-hash://{self.run}/{name}"

    def text(self, body: str) -> str:
        """Tag a body with the run id so its chunks are recognizable."""
        return f"{body} Reference {self.run}."

    async def document_chunks(self, name: str) -> set[tuple[bool, Any]]:
        """Return (open, content hash) for each chunk linked to one document."""
        rows = await self.store.execute_read(
            "MATCH (:Document {document_key: $key})-[r:HAS_PART]->(c:Chunk) "
            "RETURN r.invalid_at IS NULL AS open, c.content_hash AS content_hash",
            {"key": self.key(name)},
        )
        return {(bool(row["open"]), row["content_hash"]) for row in rows}


async def _cleanup(env: _Env) -> None:
    """Remove only the nodes this run created."""
    store = env.store
    await store.execute_write(
        "MATCH (c:Chunk) WHERE c.text CONTAINS $run DETACH DELETE c",
        {"run": env.run},
    )
    await store.execute_write(
        "MATCH (d:Document) WHERE d.document_key STARTS WITH $prefix DETACH DELETE d",
        {"prefix": env.key("")},
    )
    await store.execute_write(
        "MATCH (j:CutoverJob) WHERE j.document_key STARTS WITH $prefix DETACH DELETE j",
        {"prefix": env.key("")},
    )


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestChunkContentHash:
    """Chunk nodes record the content hash of the version they were cut from."""

    @pytest.fixture
    async def env(self) -> AsyncGenerator[_Env, None]:
        """Open a graph with fake models and a run-scoped key space."""
        run = uuid4().hex[:8]
        schema = GraphSchema(
            name="content_hash", version="1", entities=[], relations=[]
        )
        store = build_test_store()
        graph = await Graph.open(
            schema=schema,
            graph_store=store,
            embedder=_ConstantEmbedder(),
            extractor=_NoEntityExtractor(),
        )
        env = _Env(run=run, store=store, graph=graph)
        try:
            yield env
        finally:
            try:
                await _cleanup(env)
            finally:
                await store.close()

    async def test_every_chunk_of_an_added_document_records_its_content_hash(
        self, env: _Env
    ) -> None:
        """Each chunk node carries the hash of its own document's text."""
        first = env.text("Aspirin relieves headache.")
        second = env.text("Ibuprofen relieves fever.")

        await env.graph.add(
            documents=[_document(env.key("a"), first), _document(env.key("b"), second)]
        )

        assert await env.document_chunks("a") == {(True, _sha256(first))}
        assert await env.document_chunks("b") == {(True, _sha256(second))}

    async def test_superseded_chunks_keep_the_old_hash_after_an_update(
        self, env: _Env
    ) -> None:
        """Closed chunks keep the old hash and the new chunks take the new one."""
        key = env.key("a")
        old_text = env.text("Aspirin relieves headache.")
        new_text = env.text("Naproxen relieves inflammation.")
        await env.graph.add(documents=[_document(key, old_text)])

        updated = await env.graph.update(key, text=new_text)

        assert updated.no_op is False
        assert await env.document_chunks("a") == {
            (False, _sha256(old_text)),
            (True, _sha256(new_text)),
        }
