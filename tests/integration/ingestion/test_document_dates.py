"""Verify document dates persist and clear through the graph lifecycle."""

import hashlib
import importlib.util
import unicodedata
from collections.abc import Sequence
from datetime import date
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.default_schema import DEFAULT_SCHEMA
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from tests.integration.e2e._artifact import write_artifact


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _FixedEmbedder(Embedder):
    """Return deterministic vectors for document lifecycle tests."""

    model = "fixed"

    async def dimensions(self) -> int:
        """Return the vector size."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one fixed vector for each input text."""
        return [[0.1] * 4 for _ in texts]


class _NoopExtractor(Extractor):
    """Skip entity extraction in document lifecycle tests."""

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return no extracted entities or relations."""
        return ExtractionResult(entities=[], relations=[], extractor_name="noop")


def _document(key: str, text: str) -> Document:
    """Build a document with stable identity and source dates."""
    normalized = unicodedata.normalize("NFKC", text)
    return Document(
        text=normalized,
        title="dated document",
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        loader_name="inline",
        encoding="utf-8",
        char_count=len(normalized),
        line_count=normalized.count("\n") + 1,
        published_at=date(2024, 5, 1),
        content_date=date(2023, 12, 31),
    )


async def _open_graph(store: GraphStore) -> Graph:
    """Open a graph with deterministic ingestion dependencies."""
    return await Graph.open(
        schema=DEFAULT_SCHEMA,
        graph_store=store,
        embedder=_FixedEmbedder(),
        extractor=_NoopExtractor(),
    )


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestDocumentDates:
    """Exercise date persistence through Graph.add() and Graph.update()."""

    async def test_dates_commit_clear_and_do_not_refresh_on_noop(self) -> None:
        """Dates persist on add, clear on content change, and survive a no-op."""
        store = build_graph_store("neo4j")
        await store.connect()
        graph = await _open_graph(store)
        key = f"dates://{uuid4().hex}"
        original_text = "dated content remains stable. " * 60
        try:
            await graph.add(documents=[_document(key, original_text)])

            rows = await store.execute_read(
                "MATCH (d:Document {document_key: $key}) "
                "RETURN d.published_at AS published_at, "
                "d.content_date AS content_date",
                {"key": key},
            )
            assert rows[0] == {
                "published_at": "2024-05-01",
                "content_date": "2023-12-31",
            }
            added_dates = rows[0]

            unchanged = await graph.update(key, text=original_text)

            assert unchanged.no_op is True
            rows = await store.execute_read(
                "MATCH (d:Document {document_key: $key}) "
                "RETURN d.published_at AS published_at, "
                "d.content_date AS content_date",
                {"key": key},
            )
            assert rows[0] == {
                "published_at": "2024-05-01",
                "content_date": "2023-12-31",
            }

            changed = await graph.update(key, text="replacement dated content. " * 60)

            assert changed.no_op is False
            rows = await store.execute_read(
                "MATCH (d:Document {document_key: $key}) "
                "RETURN d.published_at AS published_at, "
                "d.content_date AS content_date",
                {"key": key},
            )
            assert rows[0] == {"published_at": None, "content_date": None}
            artifact = write_artifact(
                "document_dates",
                {
                    "added": added_dates,
                    "date_only_update_no_op": unchanged.no_op,
                    "content_update_no_op": changed.no_op,
                    "after_content_update": rows[0],
                },
            )
            assert artifact["after_content_update"] == {
                "published_at": None,
                "content_date": None,
            }
        finally:
            await store.execute_write(
                "MATCH (d:Document {document_key: $key}) "
                "OPTIONAL MATCH (d)-[:HAS_PART]->(c:Chunk) "
                "DETACH DELETE d, c",
                {"key": key},
            )
            await store.close()
