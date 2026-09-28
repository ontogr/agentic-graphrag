"""Integration proof that Graph.add emits one connected trace.

Runs ``Graph.add()`` over a two-file directory through a real Neo4j store
with a fake extractor: one file yields three Organization mentions (two
verbatim, one trailing-"s" variant clearing the fuzzy fast path), the
other raises under ``ErrorPolicy.SKIP``. A real SDK ``TracerProvider``
with an in-memory exporter records the run. The captured span tree goes
to a JSON artifact for hand inspection.
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
from opentelemetry.trace import StatusCode

from agrag.common.data_models.chunk import Chunk as ChunkModel
from agrag.common.data_models.extraction import ExtractedEntity, ExtractionResult
from agrag.common.data_models.graph_schema import GENERIC, GraphSchema
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.loaders.corpus.types import ErrorPolicy


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _MockEmbedder(Embedder):
    """Embedder that returns a fixed vector."""

    model = "fake"

    async def dimensions(self) -> int:
        """Return fixed dimensions."""
        return 3

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a constant vector for each input text."""
        return [[1.0, 2.0, 3.0] for _ in texts]


class _MarkerExtractor(Extractor):
    """Extractor keyed off a marker substring in the chunk text.

    A chunk carrying ``MERIDIAN_MARKER`` yields two verbatim mentions and
    one trailing-"s" variant; a chunk carrying ``FAILURE_MARKER`` raises.
    Mention names carry the run suffix so reruns never share entities.
    """

    def __init__(self, suffix: str) -> None:
        """Remember the suffix isolating this run's mentions."""
        self._suffix = suffix

    async def extract(self, chunk: ChunkModel, schema: GraphSchema) -> ExtractionResult:
        """Return canned mentions or raise, by marker."""
        if "FAILURE_MARKER" in chunk.text:
            raise RuntimeError("fake extraction boom")
        if "MERIDIAN_MARKER" in chunk.text:
            base = f"Meridian Health Group {self._suffix}"
            names = [base, base, f"{base}s"]
            return ExtractionResult(
                entities=[
                    ExtractedEntity(
                        chunk_id=chunk.id,  # type: ignore[arg-type]
                        label="Organization",
                        text=name,
                        char_start=0,
                        char_end=len(name),
                    )
                    for name in names
                ],
                relations=[],
                extractor_name="marker",
            )
        raise AssertionError(f"unexpected chunk text: {chunk.text!r}")


def _write_fixtures(directory: Path) -> tuple[str, str]:
    """Write the two single-chunk files, returning their resolved uris."""
    meridian = directory / "meridian.txt"
    meridian.write_text(
        "MERIDIAN_MARKER. Meridian Health Group opened a new downtown clinic "
        "with extended hours for returning patients and their families."
    )
    failure = directory / "failure.txt"
    failure.write_text(
        "FAILURE_MARKER. This file never extracts; its chunk always fails."
    )
    assert len(meridian.read_text()) < 1024
    assert len(failure.read_text()) < 1024
    return str(meridian.resolve()), str(failure.resolve())


async def _cleanup(store: Any, uris: Sequence[str], suffix: str) -> None:
    """Delete only this run's nodes: its documents plus suffixed names."""
    await store.execute_write(
        "MATCH (d:Document) WHERE d.uri IN $uris "
        "OPTIONAL MATCH (d)-[:PART_OF]->(c:Chunk) "
        "DETACH DELETE d, c",
        {"uris": list(uris)},
    )
    await store.execute_write(
        "MATCH (e:Organization) WHERE e.name CONTAINS $suffix DETACH DELETE e",
        {"suffix": suffix},
    )
    await store.execute_write(
        "MATCH (r:ResolvedEntity) WHERE r.name CONTAINS $suffix DETACH DELETE r",
        {"suffix": suffix},
    )
    await store.execute_write(
        "MATCH (a:_AgragMergeAlias) WHERE a.merge_key CONTAINS $key DETACH DELETE a",
        {"key": suffix.lower()},
    )


def _span_tree_path() -> Path:
    """Return the artifact path for the captured span tree."""
    root = Path(__file__).resolve().parents[3]
    directory = root / "reports" / "ingestion"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "add_span_tracing.json"


def _write_span_tree(path: Path, spans: Sequence[ReadableSpan]) -> None:
    """Write the captured span tree artifact, verifying the round trip."""
    payload: dict[str, Any] = {
        "spans": [
            {
                "id": span.context.span_id,
                "trace_id": format(span.context.trace_id, "032x"),
                "parent_id": span.parent.span_id if span.parent else None,
                "name": span.name,
                "attributes": dict(span.attributes or {}),
                "status": span.status.status_code.name,
            }
            for span in spans
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    assert json.loads(path.read_text()) == payload


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestAddSpanTracing:
    """Graph.add nests its whole pipeline under one root span."""

    async def test_add_emits_single_connected_trace(self, tmp_path: Path) -> None:
        """Load, chunk, extract, cutover, and storage share one trace."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        suffix = uuid4().hex[:8]
        run = tmp_path / f"add-span-{suffix}"
        run.mkdir()
        uris = _write_fixtures(run)

        store = build_graph_store("neo4j")
        await store.connect()
        graph = await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=_MockEmbedder(),
            extractor=_MarkerExtractor(suffix),
            tracer=provider.get_tracer("agrag-test"),
        )
        try:
            exporter.clear()
            result = await graph.add(source=run, error_policy=ErrorPolicy.SKIP)
            spans = list(exporter.get_finished_spans())
            by_name: dict[str, list[ReadableSpan]] = {}
            for span in spans:
                by_name.setdefault(span.name, []).append(span)

            trace_ids = {span.context.trace_id for span in spans}
            assert len(trace_ids) == 1
            roots = [span for span in spans if span.parent is None]
            assert len(roots) == 1
            assert roots[0].name == "agrag.ingestion.add"

            for name in (
                "agrag.ingestion.load_document",
                "agrag.ingestion.chunk_document",
                "agrag.extraction.extract_chunk",
                "agrag.ingestion.cutover_job",
                "agrag.ingestion.ingest_chunks",
            ):
                assert by_name.get(name), f"no {name} span was captured"
            assert len(by_name["agrag.extraction.extract_chunk"]) == 2

            (failure,) = result.extraction.failures
            assert failure.trace_id is not None
            assert failure.span_id is not None
            failed_spans = [
                span
                for span in by_name["agrag.extraction.extract_chunk"]
                if format(span.context.span_id, "016x") == failure.span_id
            ]
            assert len(failed_spans) == 1
            assert failed_spans[0].status.status_code is StatusCode.ERROR
            assert any(
                "fake extraction boom"
                in str((event.attributes or {}).get("exception.message", ""))
                for event in failed_spans[0].events or []
            )

            merge_groups = [
                span
                for span in by_name.get("agrag.merge.merge_group", [])
                if (span.attributes or {}).get("agrag.mention_count") == 2
            ]
            assert len(merge_groups) == 1
            assert by_name.get("agrag.merge.materialize_component"), (
                "the fuzzy-match materialization loop never ran"
            )

            _write_span_tree(_span_tree_path(), spans)
        finally:
            await _cleanup(store, uris, suffix)
            await store.close()

    async def test_add_without_tracer_leaves_failure_ids_empty(
        self, tmp_path: Path
    ) -> None:
        """A tracer=None run records no ids on its extraction failure."""
        suffix = uuid4().hex[:8]
        run = tmp_path / f"add-untraced-{suffix}"
        run.mkdir()
        uris = _write_fixtures(run)

        store = build_graph_store("neo4j")
        await store.connect()
        graph = await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=_MockEmbedder(),
            extractor=_MarkerExtractor(suffix),
        )
        try:
            result = await graph.add(source=run, error_policy=ErrorPolicy.SKIP)
            (failure,) = result.extraction.failures
            assert failure.trace_id is None
        finally:
            await _cleanup(store, uris, suffix)
            await store.close()
