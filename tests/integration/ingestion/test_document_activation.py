"""Integration tests for the per-document activation log.

Each committed change to a document writes one DocumentActivation node in the
same transaction that flips its HAS_PART edges, and the Document node counts
them in ``activation_seq``. Re-adding unchanged content, forced in-place
refreshes and metadata-only updates write no activation. The tests use a real
Neo4j instance with a fixed embedder and an extractor that emits no entities.
"""

import hashlib
import importlib.util
import unicodedata
from collections.abc import AsyncGenerator, Sequence
from datetime import date
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.default_schema import DEFAULT_SCHEMA
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.update_decision import UpdateDecision
from agrag.cypher.relations import relationship_types_from_query
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.loaders.common import text_sections
from tests.conftest import FAKE_EMBEDDING_DIMENSIONS


neo4j_missing = importlib.util.find_spec("neo4j") is None

_ACTIVATIONS = (
    "MATCH (:Document {document_key: $key})-[:HAS_ACTIVATION]->"
    "(a:DocumentActivation) "
    "RETURN a.activation_seq AS seq, a.verb AS verb, "
    "a.content_hash AS content_hash, "
    "a.previous_content_hash AS previous_content_hash, "
    "a.version_id AS version_id, a.document_key AS document_key "
    "ORDER BY a.activation_seq"
)


class _FixedEmbedder(Embedder):
    """Embedder returning 4-dimension vectors and failing on a marker text."""

    model = "fixed"

    def __init__(self) -> None:
        """Start with no failure marker."""
        self.fail_marker: str | None = None

    async def dimensions(self) -> int:
        """Return 4 dimensions."""
        return FAKE_EMBEDDING_DIMENSIONS

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a constant vector, or raise when a text holds the marker."""
        for text in texts:
            if self.fail_marker is not None and self.fail_marker in text:
                raise RuntimeError("embedder unavailable")
        return [[0.1] * FAKE_EMBEDDING_DIMENSIONS for _ in texts]


class _NoopExtractor(Extractor):
    """Extractor that emits no entities or relations."""

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return an empty extraction result."""
        return ExtractionResult(entities=[], relations=[], extractor_name="noop")


def _content_hash(text: str) -> str:
    """Hash text the way the inline walk and update() do."""
    return hashlib.sha256(
        unicodedata.normalize("NFKC", text).encode("utf-8")
    ).hexdigest()


def _document(key: str, text: str) -> Document:
    """Build a prose Document with an explicit stable key."""
    normalized = unicodedata.normalize("NFKC", text)
    return Document(
        text=normalized,
        title="activation",
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=_content_hash(normalized),
        loader_name="inline",
        encoding="utf-8",
        char_count=len(normalized),
        line_count=normalized.count("\n") + 1,
        sections=text_sections(normalized),
    )


class _Env:
    """One graph store, graph and embedder, scoped to one run id."""

    def __init__(
        self,
        store: GraphStore,
        graph: Graph,
        embedder: _FixedEmbedder,
        run: str,
    ) -> None:
        """Hold the handles one test uses."""
        self.store = store
        self.graph = graph
        self.embedder = embedder
        self.run = run

    def key(self, name: str) -> str:
        """Return the document key for a short name."""
        return f"activation://{self.run}/{name}"

    def text(self, body: str) -> str:
        """Tag a body with the run id so its chunks are recognizable."""
        return f"{body} Reference {self.run}."

    async def activations(self, name: str) -> list[dict[str, object]]:
        """Return the activation rows of one document, ordered by sequence."""
        rows = await self.store.execute_read(_ACTIVATIONS, {"key": self.key(name)})
        return [dict(row) for row in rows]

    async def activation_seq(self, name: str) -> int | None:
        """Return the stored activation_seq of one document, or None when absent."""
        rows = await self.store.execute_read(
            "MATCH (d:Document {document_key: $key}) RETURN d.activation_seq AS seq",
            {"key": self.key(name)},
        )
        if not rows or rows[0]["seq"] is None:
            return None
        return int(rows[0]["seq"])

    async def open_chunk_ids(self, name: str) -> set[str]:
        """Return the ids of chunks behind open HAS_PART edges of one document."""
        rows = await self.store.execute_read(
            "MATCH (:Document {document_key: $key})-[r:HAS_PART]->(c:Chunk) "
            "WHERE r.invalid_at IS NULL RETURN c.id AS id",
            {"key": self.key(name)},
        )
        return {str(row["id"]) for row in rows}

    async def all_chunk_ids(self, name: str) -> set[str]:
        """Return the ids of every chunk linked to one document, open or closed."""
        rows = await self.store.execute_read(
            "MATCH (:Document {document_key: $key})-[:HAS_PART]->(c:Chunk) "
            "RETURN c.id AS id",
            {"key": self.key(name)},
        )
        return {str(row["id"]) for row in rows}


async def _cleanup(store: GraphStore, prefix: str) -> None:
    """Remove the documents, chunks, activations and jobs of one run."""
    await store.execute_write(
        "MATCH (d:Document) WHERE d.document_key STARTS WITH $prefix "
        "OPTIONAL MATCH (d)-[:HAS_PART]->(part) "
        "OPTIONAL MATCH (d)-[:HAS_ACTIVATION]->(a:DocumentActivation) "
        "DETACH DELETE d, part, a",
        {"prefix": prefix},
    )
    await store.execute_write(
        "MATCH (j:CutoverJob) WHERE j.document_key STARTS WITH $prefix DETACH DELETE j",
        {"prefix": prefix},
    )


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestDocumentActivation:
    """Every committed document change is recorded once, in order."""

    @pytest.fixture
    async def env(self) -> AsyncGenerator[_Env, None]:
        """Open a graph and a store, and remove this run's rows afterwards."""
        run = uuid4().hex[:8]
        store = build_graph_store("neo4j")
        embedder = _FixedEmbedder()
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=embedder,
            extractor=_NoopExtractor(),
        )
        handles = _Env(store=store, graph=graph, embedder=embedder, run=run)
        try:
            yield handles
        finally:
            try:
                await _cleanup(store, f"activation://{run}/")
            finally:
                await store.close()

    async def test_revert_records_each_change_in_order(self, env: _Env) -> None:
        """A to B to A records three activations and keeps A's chunks current."""
        key = env.key("doc")
        text_a = env.text("Alpha activation probe, first version.")
        text_b = env.text("Bravo activation probe, second version.")

        first = await env.graph.add(
            documents=[_document(key, text_a)], return_chunks=True
        )
        chunks_a = {str(chunk.id) for chunk in first.chunks}
        assert chunks_a
        await env.graph.update(key, text=text_b)
        chunks_after_b = await env.all_chunk_ids("doc")
        reverted = await env.graph.update(key, text=text_a)

        assert reverted.no_op is False
        activations = await env.activations("doc")
        assert [row["seq"] for row in activations] == [1, 2, 3]
        assert [row["verb"] for row in activations] == ["add", "update", "update"]
        assert [row["content_hash"] for row in activations] == [
            _content_hash(text_a),
            _content_hash(text_b),
            _content_hash(text_a),
        ]
        assert [row["previous_content_hash"] for row in activations] == [
            None,
            _content_hash(text_a),
            _content_hash(text_b),
        ]
        assert activations[0]["version_id"] == activations[2]["version_id"]
        assert activations[0]["version_id"] != activations[1]["version_id"]
        assert await env.activation_seq("doc") == 3
        assert await env.all_chunk_ids("doc") == chunks_after_b
        assert await env.open_chunk_ids("doc") == chunks_a

    async def test_delete_records_activation_without_hash(self, env: _Env) -> None:
        """Deleting a document records a delete with no content hash."""
        key = env.key("doc")
        text = env.text("Charlie activation probe, deleted later.")
        await env.graph.add(documents=[_document(key, text)])

        deleted = await env.graph.delete_document(key)
        again = await env.graph.delete_document(key)

        assert deleted.no_op is False
        assert again.parts_closed == 0
        activations = await env.activations("doc")
        assert [row["seq"] for row in activations] == [1, 2]
        removal = activations[1]
        assert removal["verb"] == "delete"
        assert removal["content_hash"] is None
        assert removal["version_id"] is None
        assert removal["previous_content_hash"] == _content_hash(text)
        assert await env.activation_seq("doc") == 2
        assert await env.open_chunk_ids("doc") == set()

    async def test_repeat_add_is_skipped_and_changed_add_is_an_update(
        self, env: _Env
    ) -> None:
        """Adding the same key again changes nothing, and new text is a new version."""
        key = env.key("doc")
        text = env.text("Delta activation probe.")
        changed = env.text("Echo activation probe, edited.")
        first = await env.graph.add(
            documents=[_document(key, text)], return_chunks=True
        )
        open_before = await env.open_chunk_ids("doc")
        assert open_before == {str(chunk.id) for chunk in first.chunks}

        repeated = await env.graph.add(documents=[_document(key, text)])

        assert repeated.ingestion.unchanged == 1
        assert repeated.storage.nodes_written == 0
        assert repeated.chunks == []
        assert await env.open_chunk_ids("doc") == open_before
        assert len(await env.activations("doc")) == 1

        await env.graph.add(documents=[_document(key, changed)])

        assert await env.open_chunk_ids("doc") != open_before
        activations = await env.activations("doc")
        assert [row["seq"] for row in activations] == [1, 2]
        assert activations[1]["verb"] == "update"
        assert activations[1]["previous_content_hash"] == _content_hash(text)
        assert activations[1]["content_hash"] == _content_hash(changed)

    async def test_failed_pending_phase_leaves_no_activation(self, env: _Env) -> None:
        """A failed update records nothing, and its retry records one change."""
        key = env.key("doc")
        before = env.text("Foxtrot activation probe, committed.")
        bad = env.text("Golf activation probe. Explode.")
        after = env.text("Hotel activation probe, retried.")
        await env.graph.add(documents=[_document(key, before)])

        env.embedder.fail_marker = "Explode"
        with pytest.raises(RuntimeError, match="embedder unavailable"):
            await env.graph.update(key, text=bad)

        assert await env.activation_seq("doc") == 1
        assert len(await env.activations("doc")) == 1

        env.embedder.fail_marker = None
        await env.graph.update(key, text=after)

        activations = await env.activations("doc")
        assert [row["seq"] for row in activations] == [1, 2]
        assert activations[1]["content_hash"] == _content_hash(after)
        assert await env.activation_seq("doc") == 2

    async def test_in_place_refresh_and_metadata_update_write_no_activation(
        self, env: _Env
    ) -> None:
        """Changes that keep the content do not bump the sequence."""
        key = env.key("doc")
        text = env.text("India activation probe, refreshed in place.")
        await env.graph.add(documents=[_document(key, text)])

        refreshed = await env.graph.update(key, text=text, force=True)
        dated = _document(key, text).model_copy(
            update={"published_at": date(2026, 1, 1)}
        )
        metadata = await env.graph.update(key, document=dated)

        assert refreshed.decision is UpdateDecision.IN_PLACE
        assert metadata.decision is UpdateDecision.METADATA_ONLY
        assert len(await env.activations("doc")) == 1
        assert await env.activation_seq("doc") == 1

    async def test_relation_listing_skips_activation_edges(self, env: _Env) -> None:
        """A relation listing from the document never returns its activation edges."""
        key = env.key("doc")
        await env.graph.add(documents=[_document(key, env.text("Juliet probe."))])
        await env.graph.update(key, text=env.text("Kilo probe."))
        rows = await env.store.execute_read(
            "MATCH (d:Document {document_key: $key}) RETURN d.id AS id",
            {"key": key},
        )
        document_id = str(rows[0]["id"])
        assert len(await env.activations("doc")) == 2

        listing = await env.store.execute_read(
            relationship_types_from_query(direction="both"),
            {"seed_ids": [document_id], "job_id": None},
        )

        assert listing == []
