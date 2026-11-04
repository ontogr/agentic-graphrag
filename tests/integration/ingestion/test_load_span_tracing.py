"""Integration proof that loader spans never parent chunk spans.

Runs ``Graph.add()`` over a generated JSONL fixture with more than 100 rows
through a real Neo4j store, so ``_CorpusWalk``'s default ``batch_size=100``
flushes mid-source. A real SDK ``TracerProvider`` with an in-memory exporter
records the run. The captured span tree goes to a JSON artifact for hand
inspection.

The same module also checks that a slow loader leaves the event loop free
during ``Graph.add()``.
"""

import asyncio
import importlib.util
import json
import time
from collections.abc import Iterator, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.common.data_models.chunk import Chunk as ChunkModel
from agrag.common.data_models.default_schema import DEFAULT_SCHEMA
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.embedding.base import Embedder
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.loaders.base import Loader
from agrag.loaders.common import build_prose_document, text_sections
from agrag.loaders.types import ReadOptions, SourceRef
from tests.conftest import FAKE_EMBEDDING_DIMENSIONS
from tests.integration._backend import build_test_store


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _MockEmbedder(Embedder):
    """Embedder that returns a fixed vector."""

    model = "fake"

    async def dimensions(self) -> int:
        """Return fixed dimensions."""
        return FAKE_EMBEDDING_DIMENSIONS

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a constant vector for each input text."""
        return [[1.0, 2.0, 3.0, 4.0] for _ in texts]


class _MockExtractor(Extractor):
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
class _SlowTextLoader(Loader):
    """Holds the CPU for a fixed time, then yields one text document.

    The window in which the CPU is held is recorded, so the test can compare it
    with the event loop's activity during the same period.
    """

    extensions = frozenset({".txt"})
    family = DocumentFamily.PROSE
    busy_seconds = 0.3

    def __init__(self) -> None:
        """Start with no recorded window."""
        self.window: tuple[float, float] | None = None

    def load(
        self,
        source: SourceRef,
        stream: BinaryIO,
        opts: ReadOptions,
        *,
        start_at: int = 0,
    ) -> Iterator[Document]:
        """Spin for ``busy_seconds``, record the window, then yield the document."""
        started = time.perf_counter()
        deadline = started + self.busy_seconds
        while time.perf_counter() < deadline:
            pass
        self.window = (started, time.perf_counter())
        text = "slow loader row " + ("content " * 20)
        yield build_prose_document(
            source=source,
            text=text,
            encoding="utf-8",
            source_format=SourceFormat.TXT,
            loader_name="slow",
            opts=opts,
            title=source.uri,
            sections=text_sections(text),
        )


class TestGraphAddLoopResponsiveness:
    """Graph.add leaves the event loop free while a loader holds the CPU."""

    async def test_event_loop_ticks_during_a_slow_loader_in_graph_add(
        self, tmp_path: Path
    ) -> None:
        """Other tasks tick inside the loader's busy window."""
        fixture = tmp_path / f"slow-loader-{uuid4().hex}.txt"
        fixture.write_text("unused", encoding="utf-8")
        source_uri = str(fixture.resolve())
        loader = _SlowTextLoader()
        ticks: list[float] = []

        async def tick() -> None:
            while True:
                ticks.append(time.perf_counter())
                await asyncio.sleep(0.01)

        store = build_test_store()
        await store.connect()
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_MockEmbedder(),
            extractor=_MockExtractor(),
        )
        ticker = asyncio.create_task(tick())
        try:
            await graph.add(source=fixture, loader=loader)
        finally:
            ticker.cancel()
            with suppress(asyncio.CancelledError):
                await ticker
            await store.execute_write(
                "MATCH (d:Document) WHERE d.uri = $uri "
                "OPTIONAL MATCH (d)-[:HAS_PART]->(c:Chunk) "
                "DETACH DELETE d, c",
                {"uri": source_uri},
            )
            await store.close()

        assert loader.window is not None, "the loader never ran"
        start, end = loader.window
        inside = [moment for moment in ticks if start < moment < end]
        assert len(inside) >= 5, "the event loop did not run during the loader's work"


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

        store = build_test_store()
        await store.connect()
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_MockEmbedder(),
            extractor=_MockExtractor(),
            tracer=provider.get_tracer("agrag-test"),
        )
        try:
            await graph.add(source=fixture)
        finally:
            await store.execute_write(
                "MATCH (d:Document) WHERE d.uri = $uri "
                "OPTIONAL MATCH (d)-[:HAS_PART]->(c:Chunk) "
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
