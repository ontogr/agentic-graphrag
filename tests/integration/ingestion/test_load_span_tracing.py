"""Integration proof that loader spans never parent chunk spans.

Runs ``Graph.add()`` over a generated JSONL fixture with more than 100 rows
through a real Neo4j store, so ``_CorpusWalk``'s default ``batch_size=100``
flushes mid-source. A real SDK ``TracerProvider`` with an in-memory exporter
records the run. The captured span tree goes to a JSON artifact for hand
inspection.
"""

import importlib.util
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.common.data_models.chunk import Chunk as ChunkModel
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_schema import GENERIC, GraphSchema
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph


neo4j_missing = importlib.util.find_spec("neo4j") is None


class MockEmbedder(Embedder):
    """Embedder that returns a fixed vector."""

    model = "fake"

    async def dimensions(self) -> int:
        """Return fixed dimensions."""
        return 3

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a constant vector for each input text."""
        return [[1.0, 2.0, 3.0] for _ in texts]


class MockExtractor(Extractor):
    """Extractor that returns a canned result and records calls."""

    def __init__(self, result: ExtractionResult | None = None) -> None:
        """Create the fake extractor."""
        self.result = result or ExtractionResult(
            entities=[], relations=[], extractor_name="fake"
        )
        self.calls: list[str] = []

    async def extract(self, chunk: ChunkModel, schema: GraphSchema) -> ExtractionResult:
        """Record the chunk text and return the canned result."""
        self.calls.append(chunk.text)
        return self.result


def _write_jsonl_fixture(path: Path, rows: int = 120) -> None:
    """Write one JSON object per line with a text field."""
    lines = [
        json.dumps({"text": f"load span row {index} " + ("content " * 20)})
        for index in range(rows)
    ]
    path.write_text("\n".join(lines) + "\n")


def _span_tree_path() -> Path:
    """Return the artifact path for the captured span tree."""
    root = Path(__file__).resolve().parents[3]
    directory = root / "reports" / "ingestion"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "load_span_tracing.json"


def _ancestors(span: ReadableSpan, by_id: dict[int, ReadableSpan]) -> set[int]:
    """Return every ancestor span id above the given span."""
    found: set[int] = set()
    while span.parent is not None and span.parent.span_id in by_id:
        span = by_id[span.parent.span_id]
        found.add(span.context.span_id)
    return found


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestLoadSpanTracing:
    """Graph.add emits load spans that never parent chunk spans."""

    async def test_chunk_spans_never_nest_under_load_spans(
        self, tmp_path: Path
    ) -> None:
        """A mid-source yield leaves chunking outside any load span."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        fixture = tmp_path / f"load-span-{uuid4().hex}.jsonl"
        _write_jsonl_fixture(fixture)
        source_uri = str(fixture.resolve())

        store = build_graph_store("neo4j")
        await store.connect()
        graph = await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=MockEmbedder(),
            extractor=MockExtractor(),
            tracer=provider.get_tracer("agrag-test"),
        )
        try:
            await graph.add(source=fixture)
        finally:
            await store.execute_write(
                "MATCH (d:Document) WHERE d.uri = $uri "
                "OPTIONAL MATCH (d)-[:PART_OF]->(c:Chunk) "
                "DETACH DELETE d, c",
                {"uri": source_uri},
            )
            await store.close()

        spans = list(exporter.get_finished_spans())
        by_id = {span.context.span_id: span for span in spans}
        load_spans = [
            span for span in spans if span.name == "agrag.ingestion.load_document"
        ]
        same_source = [
            span
            for span in load_spans
            if (span.attributes or {}).get("agrag.source_uri") == source_uri
        ]
        assert len(same_source) > 1, "the walk never crossed a batch boundary"
        chunk_spans = [
            span for span in spans if span.name.startswith("agrag.ingestion.chunk_")
        ]
        assert chunk_spans, "no chunk spans were captured"
        load_ids = {span.context.span_id for span in load_spans}
        for span in chunk_spans:
            assert not (load_ids & _ancestors(span, by_id)), (
                f"{span.name} nests under a load_document span"
            )

        payload: dict[str, Any] = {
            "source_uri": source_uri,
            "spans": [
                {
                    "id": span.context.span_id,
                    "parent_id": span.parent.span_id if span.parent else None,
                    "name": span.name,
                    "attributes": dict(span.attributes or {}),
                }
                for span in spans
            ],
        }
        path = _span_tree_path()
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        assert json.loads(path.read_text()) == payload
