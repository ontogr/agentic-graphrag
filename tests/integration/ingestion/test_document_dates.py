"""Verify document dates persist and clear through the graph lifecycle."""

import hashlib
import importlib.util
import unicodedata
from collections.abc import Iterator, Sequence
from datetime import date
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.default_schema import DEFAULT_SCHEMA
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.update_decision import UpdateDecision
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.loaders.base import ProseLoader
from agrag.loaders.types import ReadOptions, SourceRef
from tests.conftest import FAKE_EMBEDDING_DIMENSIONS
from tests.integration._backend import build_test_store
from tests.integration.e2e._artifact import write_artifact


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _FixedEmbedder(Embedder):
    """Return deterministic vectors for document lifecycle tests."""

    model = "fixed"

    def __init__(self) -> None:
        self.texts: list[str] = []

    async def dimensions(self) -> int:
        """Return the vector size."""
        return FAKE_EMBEDDING_DIMENSIONS

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one fixed vector for each input text."""
        self.texts.extend(texts)
        return [[0.1] * FAKE_EMBEDDING_DIMENSIONS for _ in texts]


class _NoopExtractor(Extractor):
    """Skip entity extraction in document lifecycle tests."""

    def __init__(self) -> None:
        self.calls = 0

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return no extracted entities or relations."""
        self.calls += 1
        return ExtractionResult(entities=[], relations=[], extractor_name="noop")


class _DatedLoader(ProseLoader):
    """Load one fixed document with dates controlled by the test."""

    extensions = frozenset({".dated"})

    def __init__(self, key: str, text: str) -> None:
        self.document = _document(key, text)

    def load(
        self,
        source: SourceRef,
        stream: BinaryIO,
        opts: ReadOptions,
        *,
        start_at: int = 0,
    ) -> Iterator[Document]:
        yield self.document.model_copy(
            update={
                "published_at": self.published_at,
                "content_date": self.content_date,
            }
        )

    published_at: date | None = date(2024, 5, 1)
    content_date: date | None = date(2023, 12, 31)


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


async def _open_graph(
    store: GraphStore, embedder: _FixedEmbedder, extractor: _NoopExtractor
) -> Graph:
    """Open a graph with deterministic ingestion dependencies."""
    return await Graph.open(
        schema=DEFAULT_SCHEMA,
        graph_store=store,
        embedder=embedder,
        extractor=extractor,
    )


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestDocumentDates:
    """Exercise date persistence through Graph.add() and Graph.update()."""

    async def test_dates_persist_and_clear_on_content_change(
        self, tmp_path: Path
    ) -> None:
        """Dates persist on add, survive a no-op, and clear on content change."""
        store = build_test_store()
        await store.connect()
        embedder = _FixedEmbedder()
        extractor = _NoopExtractor()
        graph = await _open_graph(store, embedder, extractor)
        key = f"dates://{uuid4().hex}"
        original_text = "dated content remains stable. " * 60
        source = tmp_path / "unchanged.dated"
        source.write_text("source")
        loader = _DatedLoader(key, original_text)
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

            unchanged = await graph.update(key, source=source, loader=loader)

            assert unchanged.no_op is True
            assert unchanged.decision == UpdateDecision.NO_OP
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
            assert changed.decision == UpdateDecision.NEW_VERSION
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
                    "unchanged_update_no_op": unchanged.no_op,
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

    async def test_date_only_updates_write_metadata_without_extraction(
        self, tmp_path: Path
    ) -> None:
        """Date changes update only metadata and preserve stored chunk ids."""
        store = build_test_store()
        await store.connect()
        embedder = _FixedEmbedder()
        extractor = _NoopExtractor()
        graph = await _open_graph(store, embedder, extractor)
        key = f"dates://{uuid4().hex}"
        text = "date metadata stays outside extraction. " * 60
        source = tmp_path / "update.dated"
        source.write_text("source")
        loader = _DatedLoader(key, text)
        try:
            await graph.add(documents=[_document(key, text)])
            before = await store.execute_read(
                "MATCH (:Document {document_key: $key})-[:HAS_PART]->(c:Chunk) "
                "RETURN c.id AS id",
                {"key": key},
            )
            initial_calls = extractor.calls
            initial_embeds = len(embedder.texts)

            loader.published_at = date(2025, 1, 2)
            result = await graph.update(key, source=source, loader=loader)

            assert result.no_op is False
            assert result.decision == UpdateDecision.METADATA_ONLY
            assert result.parts_closed == 0
            assert result.add_result is None
            assert extractor.calls == initial_calls
            assert len(embedder.texts) == initial_embeds
            after = await store.execute_read(
                "MATCH (:Document {document_key: $key})-[:HAS_PART]->(c:Chunk) "
                "RETURN c.id AS id",
                {"key": key},
            )
            assert sorted(row["id"] for row in after) == sorted(
                row["id"] for row in before
            )
            dates = await store.execute_read(
                "MATCH (d:Document {document_key: $key}) "
                "RETURN d.published_at AS published_at, "
                "d.content_date AS content_date",
                {"key": key},
            )
            assert dates[0] == {
                "published_at": "2025-01-02",
                "content_date": "2023-12-31",
            }
            loader.content_date = date(2022, 6, 7)
            content_date_result = await graph.update(key, source=source, loader=loader)
            assert content_date_result.decision == UpdateDecision.METADATA_ONLY
            dates = await store.execute_read(
                "MATCH (d:Document {document_key: $key}) "
                "RETURN d.published_at AS published_at, "
                "d.content_date AS content_date",
                {"key": key},
            )
            assert dates[0] == {
                "published_at": "2025-01-02",
                "content_date": "2022-06-07",
            }
            loader.published_at = None
            loader.content_date = None
            clear_result = await graph.update(key, source=source, loader=loader)
            assert clear_result.decision == UpdateDecision.METADATA_ONLY
            cleared_dates = await store.execute_read(
                "MATCH (d:Document {document_key: $key}) "
                "RETURN d.published_at AS published_at, "
                "d.content_date AS content_date",
                {"key": key},
            )
            assert cleared_dates[0] == {"published_at": None, "content_date": None}
            assert extractor.calls == initial_calls
            assert len(embedder.texts) == initial_embeds
            unchanged = await graph.update(key, source=source, loader=loader)
            assert unchanged.decision == UpdateDecision.NO_OP
            artifact = write_artifact(
                "document_dates_metadata_only",
                {
                    "decision": result.decision,
                    "no_op": result.no_op,
                    "parts_closed": result.parts_closed,
                    "chunk_ids_stable": sorted(row["id"] for row in after)
                    == sorted(row["id"] for row in before),
                    "extraction_calls": extractor.calls,
                    "embedding_calls": len(embedder.texts),
                    "dates": cleared_dates[0],
                },
            )
            assert artifact["chunk_ids_stable"] is True
        finally:
            await store.execute_write(
                "MATCH (d:Document {document_key: $key}) "
                "OPTIONAL MATCH (d)-[:HAS_PART]->(c:Chunk) "
                "DETACH DELETE d, c",
                {"key": key},
            )
            await store.close()

    async def test_force_reextracts_and_preserves_chunks_until_content_changes(
        self, tmp_path: Path
    ) -> None:
        """Force reuses chunks, writes new dates, and still versions changed text."""
        store = build_test_store()
        await store.connect()
        embedder = _FixedEmbedder()
        extractor = _NoopExtractor()
        graph = await _open_graph(store, embedder, extractor)
        key = f"dates://{uuid4().hex}"
        text = "forced extraction keeps existing chunks. " * 60
        source = tmp_path / "forced.dated"
        source.write_text("source")
        loader = _DatedLoader(key, text)
        try:
            await graph.add(documents=[_document(key, text)])
            before = await store.execute_read(
                "MATCH (:Document {document_key: $key})-[:HAS_PART]->(c:Chunk) "
                "RETURN c.id AS id",
                {"key": key},
            )
            initial_calls = extractor.calls
            initial_embeds = len(embedder.texts)
            forced = await graph.update(key, source=source, loader=loader, force=True)
            assert forced.decision == UpdateDecision.IN_PLACE
            assert forced.no_op is False
            assert forced.parts_closed == 0
            assert extractor.calls > initial_calls
            assert len(embedder.texts) == initial_embeds
            forced_calls = extractor.calls
            loader.published_at = date(2026, 2, 3)
            forced_dates = await graph.update(
                key, source=source, loader=loader, force=True
            )
            assert forced_dates.decision == UpdateDecision.IN_PLACE
            assert extractor.calls > forced_calls
            assert len(embedder.texts) == initial_embeds
            forced_rows = await store.execute_read(
                "MATCH (d:Document {document_key: $key})-[:HAS_PART]->(c:Chunk) "
                "RETURN c.id AS id, d.published_at AS published_at",
                {"key": key},
            )
            assert sorted(row["id"] for row in forced_rows) == sorted(
                row["id"] for row in before
            )
            assert {row["published_at"] for row in forced_rows} == {"2026-02-03"}
            new_version = await graph.update(
                key, text="new version content. " * 60, force=True
            )
            assert new_version.decision == UpdateDecision.NEW_VERSION
            assert new_version.parts_closed > 0
            assert len(embedder.texts) > initial_embeds
            artifact = write_artifact(
                "document_force_refresh",
                {
                    "forced_decision": forced.decision,
                    "forced_dates_decision": forced_dates.decision,
                    "forced_content_decision": new_version.decision,
                },
            )
            assert artifact == {
                "forced_decision": "in_place",
                "forced_dates_decision": "in_place",
                "forced_content_decision": "new_version",
            }
        finally:
            await store.execute_write(
                "MATCH (d:Document {document_key: $key}) "
                "OPTIONAL MATCH (d)-[:HAS_PART]->(c:Chunk) "
                "DETACH DELETE d, c",
                {"key": key},
            )
            await store.close()
