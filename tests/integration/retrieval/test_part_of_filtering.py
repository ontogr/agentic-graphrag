"""Integration tests for PART_OF currency filtering in retrieval reads.

add() -> update() against a real Neo4j instance, then the retrieval-side
hydration queries: superseded chunks stay out, current and legacy chunks
stay in, and document-scoped entity lookup still finds live entities.
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
from agrag.common.data_models.provenance import TextProvenance
from agrag.cypher.entities import hydrate_chunks_by_id_query
from agrag.cypher.relations import entities_in_documents_query
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _FixedEmbedder(Embedder):
    """Deterministic embedder for filtering tests."""

    model = "fixed"

    async def dimensions(self) -> int:
        """Return a small fixed dimension."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a constant vector for every text."""
        return [[0.1] * 4 for _ in texts]


class _KeywordExtractor(Extractor):
    """Extractor emitting one distinctive Person mention per matching chunk."""

    def __init__(self, name: str) -> None:
        """Remember the unique probe name to mention."""
        self._name = name

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Mention the probe person when the chunk carries the keyword."""
        if "filterprobe" not in chunk.text.lower():
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


def _document(key: str, text: str) -> Document:
    """Build a prose Document carrying an explicit stable key."""
    normalized = unicodedata.normalize("NFKC", text)
    return Document(
        text=normalized,
        title="filtering",
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        loader_name="inline",
        encoding="utf-8",
        char_count=len(normalized),
        line_count=normalized.count("\n") + 1,
    )


def _legacy_chunk() -> Chunk:
    """Build a chunk with no Document node and no PART_OF edge."""
    return Chunk(
        document_id=uuid4(),
        index=0,
        text="legacy chunk without a document backbone",
        provenance=TextProvenance(char_start=0, char_end=39),
    )


def _hydrated_id(row: dict[str, object]) -> str | None:
    """Read a hydrated chunk's id from a raw driver row."""
    node = row.get("n", row)
    if isinstance(node, dict):
        properties = node.get("properties", node)
        if isinstance(properties, dict) and properties.get("id") is not None:
            return str(properties["id"])
        return None
    try:
        properties = dict(node)  # ty: ignore[no-matching-overload]  # type: ignore[arg-type]
    except Exception:
        return None
    node_id = properties.get("id")
    return str(node_id) if node_id is not None else None


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestPartOfFiltering:
    """Retrieval hydration honors PART_OF currency after an update."""

    async def _setup(self) -> tuple[Graph, GraphStore, str, str]:
        """Open a graph and ingest two versions of one probe document."""
        store = build_graph_store("neo4j")
        await store.connect()
        probe_name = f"Zzxqy Filterprobe {uuid4().hex[:8]}"
        graph = await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=_FixedEmbedder(),
            extractor=_KeywordExtractor(probe_name),
        )
        key = f"lifecycle://{uuid4().hex}"
        first_text = "filterprobe version one for hydration checks. " * 60
        second_text = "filterprobe version two, materially different. " * 60
        first = await graph.add(
            documents=[_document(key, first_text)], return_chunks=True
        )
        assert len(first.chunks) >= 1
        updated = await graph.update(key, text=second_text)
        assert updated.no_op is False
        rows = await store.execute_read(
            "MATCH (:Document {document_key: $key})-[r:PART_OF]->(c:Chunk) "
            "WHERE r.invalid_at IS NULL RETURN collect(c.id) AS open_ids",
            {"key": key},
        )
        assert len(rows[0]["open_ids"]) >= 1
        return graph, store, key, probe_name

    async def _cleanup(
        self, store: GraphStore, key: str, probe_name: str, extra_chunk_ids: list[str]
    ) -> None:
        """Remove every node this test created, including alias rows."""
        rows = await store.execute_read(
            "MATCH (e:Person {name: $name}) RETURN e.merge_key AS merge_key",
            {"name": probe_name},
        )
        merge_keys = [row["merge_key"] for row in rows if row.get("merge_key")]
        await store.execute_write(
            "MATCH (d:Document {document_key: $key}) "
            "OPTIONAL MATCH (d)-[:PART_OF]->(c:Chunk) "
            "OPTIONAL MATCH (c)-[:MENTIONED_IN]->(e:Person) "
            "DETACH DELETE d, c, e",
            {"key": key},
        )
        if extra_chunk_ids:
            await store.execute_write(
                "MATCH (c:Chunk) WHERE c.id IN $ids DETACH DELETE c",
                {"ids": extra_chunk_ids},
            )
        if merge_keys:
            await store.execute_write(
                "MATCH (a:_AgragMergeAlias) WHERE a.merge_key IN $merge_keys "
                "DETACH DELETE a",
                {"merge_keys": merge_keys},
            )
        await store.close()

    async def test_hydration_excludes_superseded_chunks(self) -> None:
        """Hydrating old and new ids returns only the current version."""
        _, store, key, probe_name = await self._setup()
        legacy_ids: list[str] = []
        try:
            rows = await store.execute_read(
                "MATCH (:Document {document_key: $key})-[r:PART_OF]->(c:Chunk) "
                "RETURN c.id AS id, r.invalid_at AS invalid_at",
                {"key": key},
            )
            old_ids = [row["id"] for row in rows if row["invalid_at"] is not None]
            new_ids = [row["id"] for row in rows if row["invalid_at"] is None]
            assert len(old_ids) >= 1
            assert len(new_ids) >= 1

            legacy = _legacy_chunk()
            await store.upsert_nodes("Chunk", [legacy.to_node_record()])
            legacy_ids = [str(legacy.id)]

            rows = await store.execute_read(
                hydrate_chunks_by_id_query(),
                {"ids": [*old_ids, *new_ids, *legacy_ids]},
            )
            returned = {_hydrated_id(row) for row in rows}
            assert set(new_ids) <= returned
            assert not (set(old_ids) & returned)
            assert set(legacy_ids) <= returned
        finally:
            await self._cleanup(store, key, probe_name, legacy_ids)

    async def test_document_entity_lookup_ignores_superseded_chunks(self) -> None:
        """Document-scoped entity lookup still finds entities via live chunks."""
        _, store, key, probe_name = await self._setup()
        try:
            rows = await store.execute_read(
                "MATCH (d:Document {document_key: $key}) RETURN d.id AS id",
                {"key": key},
            )
            rows = await store.execute_read(
                entities_in_documents_query(),
                {"document_ids": [row["id"] for row in rows]},
            )
            assert rows
        finally:
            await self._cleanup(store, key, probe_name, [])
