"""Integration tests for the Document/PART_OF version lifecycle.

add() -> update() against a real Neo4j instance: unchanged content is a
no-op, changed content closes the old PART_OF edges and opens new ones,
and the superseded Chunk nodes stay present and unmodified.
"""

import hashlib
import importlib.util
import unicodedata
from collections.abc import Sequence
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.extraction import ExtractedEntity, ExtractionResult
from agrag.common.data_models.graph_schema import GENERIC, GraphSchema
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _FixedEmbedder(Embedder):
    """Deterministic embedder for lifecycle tests."""

    model = "fixed"

    async def dimensions(self) -> int:
        """Return a small fixed dimension."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a constant vector for every text."""
        return [[0.1] * 4 for _ in texts]


class _NoopExtractor(Extractor):
    """Extractor emitting no entities, for lifecycle-only tests."""

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return no entities or relations for any chunk."""
        return ExtractionResult(entities=[], relations=[], extractor_name="noop")


class _KeywordExtractor(Extractor):
    """Extractor emitting one distinctive Person mention per matching chunk."""

    def __init__(self, name: str = "Zzxqy Deleteprobe") -> None:
        """Remember the unique probe name to mention."""
        self._name = name

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Mention the probe person when the chunk carries the keyword."""
        if "deleteprobe" not in chunk.text.lower():
            return ExtractionResult(entities=[], relations=[], extractor_name="keyword")
        mention = ExtractedEntity(
            chunk_id=chunk.id,  # type: ignore[arg-type]
            label="Person",
            text=self._name,
            char_start=0,
            char_end=len(self._name),
        )
        return ExtractionResult(
            entities=[mention], relations=[], extractor_name="keyword"
        )


def _content_hash(text: str) -> str:
    """Hash text the same way the inline walk and update() do."""
    return hashlib.sha256(
        unicodedata.normalize("NFKC", text).encode("utf-8")
    ).hexdigest()


def _document(key: str, text: str) -> Document:
    """Build a prose Document carrying an explicit stable key."""
    normalized = unicodedata.normalize("NFKC", text)
    return Document(
        text=normalized,
        title="lifecycle",
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=_content_hash(normalized),
        loader_name="inline",
        encoding="utf-8",
        char_count=len(normalized),
        line_count=normalized.count("\n") + 1,
    )


async def _open_graph(store: GraphStore) -> Graph:
    """Open a graph on an already-connected store."""
    return await Graph.open(
        schema=GENERIC,
        graph_store=store,
        embedder=_FixedEmbedder(),
        extractor=_NoopExtractor(),
    )


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestDocumentLifecycle:
    """add() -> update() closes old PART_OF edges and opens new ones."""

    async def test_update_supersedes_chunks(self) -> None:
        """Changed content closes old edges; chunks stay present and unmodified."""
        store = build_graph_store("neo4j")
        await store.connect()
        graph = await _open_graph(store)
        key = f"lifecycle://{uuid4().hex}"
        first_text = "lifecycle alpha version one. " * 60
        second_text = "lifecycle beta version two, materially different. " * 60
        try:
            first = await graph.add(
                documents=[_document(key, first_text)], return_chunks=True
            )
            old_ids = [str(chunk.id) for chunk in first.chunks]
            old_texts = {str(chunk.id): chunk.text for chunk in first.chunks}
            assert len(old_ids) >= 1

            rows = await store.execute_read(
                "MATCH (d:Document {document_key: $key})-[r:PART_OF]->(c:Chunk) "
                "RETURN count(r) AS open_edges",
                {"key": key},
            )
            assert rows[0]["open_edges"] == len(old_ids)

            updated = await graph.update(key, text=second_text)

            assert updated.no_op is False
            assert updated.previous_content_hash == _content_hash(first_text)
            assert updated.new_content_hash == _content_hash(second_text)
            assert updated.chunks_closed == len(old_ids)
            assert updated.add_result is not None

            rows = await store.execute_read(
                "MATCH (:Document {document_key: $key})-[r:PART_OF]->(c:Chunk) "
                "WHERE r.invalid_at IS NULL "
                "RETURN collect(c.id) AS open_ids",
                {"key": key},
            )
            new_ids = list(rows[0]["open_ids"])
            assert len(new_ids) >= 1
            assert set(new_ids).isdisjoint(set(old_ids))

            rows = await store.execute_read(
                "MATCH (:Document {document_key: $key})-[r:PART_OF]->(c:Chunk) "
                "WHERE c.id IN $old_ids "
                "RETURN count(r) AS total, "
                "count(CASE WHEN r.invalid_at IS NOT NULL THEN 1 END) AS closed",
                {"key": key, "old_ids": old_ids},
            )
            assert rows[0]["total"] == len(old_ids)
            assert rows[0]["closed"] == len(old_ids)

            rows = await store.execute_read(
                "MATCH (:Document {document_key: $key})-[r:PART_OF]->(c:Chunk) "
                "WHERE r.invalid_at IS NULL "
                "RETURN collect(c.id) AS open_ids",
                {"key": key},
            )
            assert set(rows[0]["open_ids"]) == set(new_ids)

            rows = await store.execute_read(
                "MATCH (c:Chunk) WHERE c.id IN $old_ids "
                "RETURN c.id AS id, c.text AS text",
                {"old_ids": old_ids},
            )
            assert {row["id"]: row["text"] for row in rows} == old_texts
        finally:
            await store.execute_write(
                "MATCH (d:Document {document_key: $key}) "
                "OPTIONAL MATCH (d)-[:PART_OF]->(c:Chunk) "
                "DETACH DELETE d, c",
                {"key": key},
            )
            await store.close()

    async def test_update_same_text_twice_is_a_no_op(self) -> None:
        """A repeated update with unchanged text writes nothing new."""
        store = build_graph_store("neo4j")
        await store.connect()
        graph = await _open_graph(store)
        key = f"lifecycle://{uuid4().hex}"
        text = "lifecycle repeated no-op check. " * 60
        try:
            first = await graph.add(
                documents=[_document(key, text)], return_chunks=True
            )
            assert len(first.chunks) >= 1

            updated = await graph.update(key, text=text)

            assert updated.no_op is True
            assert updated.chunks_closed == 0
            assert updated.add_result is None

            rows = await store.execute_read(
                "MATCH (d:Document {document_key: $key})-[r:PART_OF]->(c:Chunk) "
                "RETURN count(r) AS total, "
                "count(CASE WHEN r.invalid_at IS NULL THEN 1 END) AS open_edges",
                {"key": key},
            )
            assert rows[0]["total"] == len(first.chunks)
            assert rows[0]["open_edges"] == len(first.chunks)
        finally:
            await store.execute_write(
                "MATCH (d:Document {document_key: $key}) "
                "OPTIONAL MATCH (d)-[:PART_OF]->(c:Chunk) "
                "DETACH DELETE d, c",
                {"key": key},
            )
            await store.close()

    async def test_delete_document_prunes_entities_without_surviving_evidence(
        self,
    ) -> None:
        """Delete closes PART_OF edges, keeps chunks, and prunes orphaned entities."""
        store = build_graph_store("neo4j")
        await store.connect()
        probe_name = f"Zzxqy Deleteprobe {uuid4().hex[:8]}"
        graph = await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=_FixedEmbedder(),
            extractor=_KeywordExtractor(probe_name),
        )
        key = f"lifecycle://{uuid4().hex}"
        text = "deleteprobe provenance stays after a soft delete. " * 60
        try:
            first = await graph.add(
                documents=[_document(key, text)], return_chunks=True
            )
            old_ids = [str(chunk.id) for chunk in first.chunks]
            old_texts = {str(chunk.id): chunk.text for chunk in first.chunks}
            assert len(old_ids) >= 1
            rows = await store.execute_read(
                "MATCH (e:Person {name: $name}) RETURN count(e) AS n",
                {"name": probe_name},
            )
            assert rows[0]["n"] >= 1

            deleted = await graph.delete_document(key)

            assert deleted.no_op is False
            assert deleted.new_content_hash is None
            assert deleted.add_result is None
            assert deleted.chunks_closed == len(old_ids)
            assert deleted.previous_content_hash == _content_hash(text)

            rows = await store.execute_read(
                "MATCH (:Document {document_key: $key})-[r:PART_OF]->(c:Chunk) "
                "WHERE c.id IN $old_ids "
                "RETURN count(r) AS total, "
                "count(CASE WHEN r.invalid_at IS NOT NULL THEN 1 END) AS closed",
                {"key": key, "old_ids": old_ids},
            )
            assert rows[0]["total"] == len(old_ids)
            assert rows[0]["closed"] == len(old_ids)

            rows = await store.execute_read(
                "MATCH (d:Document {document_key: $key}) RETURN count(d) AS n",
                {"key": key},
            )
            assert rows[0]["n"] == 1

            rows = await store.execute_read(
                "MATCH (c:Chunk) WHERE c.id IN $old_ids "
                "RETURN c.id AS id, c.text AS text",
                {"old_ids": old_ids},
            )
            assert {row["id"]: row["text"] for row in rows} == old_texts

            rows = await store.execute_read(
                "MATCH (e:Person {name: $name}) RETURN count(e) AS n",
                {"name": probe_name},
            )
            assert rows[0]["n"] == 0

            again = await graph.delete_document(key)
            assert again.chunks_closed == 0
        finally:
            merge_keys = [f"Person:{probe_name.strip().casefold()}"]
            await store.execute_write(
                "MATCH (d:Document {document_key: $key}) "
                "OPTIONAL MATCH (d)-[:PART_OF]->(c:Chunk) "
                "OPTIONAL MATCH (c)-[:MENTIONED_IN]->(e:Person) "
                "DETACH DELETE d, c, e",
                {"key": key},
            )
            if merge_keys:
                await store.execute_write(
                    "MATCH (a:_AgragMergeAlias) WHERE a.merge_key IN $merge_keys "
                    "DETACH DELETE a",
                    {"merge_keys": merge_keys},
                )
            await store.close()

    async def test_repeat_add_converges_part_of_edges(self) -> None:
        """Adding identical content twice leaves one open edge per chunk."""
        store = build_graph_store("neo4j")
        await store.connect()
        graph = await _open_graph(store)
        key = f"lifecycle://{uuid4().hex}"
        text = "repeat ingestion converges on one edge set. " * 60
        try:
            first = await graph.add(
                documents=[_document(key, text)], return_chunks=True
            )
            assert len(first.chunks) >= 1
            second = await graph.add(
                documents=[_document(key, text)], return_chunks=True
            )
            assert len(second.chunks) == len(first.chunks)

            rows = await store.execute_read(
                "MATCH (:Document {document_key: $key})-[r:PART_OF]->(c:Chunk) "
                "RETURN count(r) AS total, "
                "count(CASE WHEN r.invalid_at IS NULL THEN 1 END) AS open_edges",
                {"key": key},
            )
            assert rows[0]["total"] == len(first.chunks)
            assert rows[0]["open_edges"] == len(first.chunks)
        finally:
            await store.execute_write(
                "MATCH (d:Document {document_key: $key}) "
                "OPTIONAL MATCH (d)-[:PART_OF]->(c:Chunk) "
                "DETACH DELETE d, c",
                {"key": key},
            )
            await store.close()
