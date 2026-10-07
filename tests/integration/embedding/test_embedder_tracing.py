"""Integration proof that embedders load the model once per instance.

Runs a real ``SentenceTransformerEmbedder`` and a real
``FastEmbedBM25Embedder`` through a real SDK ``TracerProvider`` with an
in-memory exporter. The first ``embed`` against an instance exports one
``agrag.embedding.model_load`` span; a second ``embed`` against the same
instance exports none. The captured span tree goes to a JSON artifact for
hand inspection.

These tests download real models from the network on first use. They
require the ``embed-local`` extra for the sentence-transformers case and
the ``qdrant`` extra for the BM25 case, plus network access. Each case
skips when its extra is not installed.
"""

import importlib.util
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.embedding.fastembed_bm25 import FastEmbedBM25Embedder
from agrag.embedding.sentence_transformers import SentenceTransformerEmbedder


embed_local_missing = importlib.util.find_spec("sentence_transformers") is None


def _tracing_provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Return a provider wired to an in-memory exporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _named(spans: Sequence[ReadableSpan], name: str) -> list[ReadableSpan]:
    """Return the captured spans with the given name."""
    return [span for span in spans if span.name == name]


def _assert_loads_once(
    spans: Sequence[ReadableSpan], model: str, *, before_second: int
) -> None:
    """Assert exactly one model_load, and none after the first call.

    ``before_second`` is the number of spans captured once the first
    ``embed`` returned. Checking that the total is unchanged afterwards is
    what makes "none on a second call" a real assertion rather than an
    inference from a combined count -- a second load would push the total
    past one and fail here.
    """
    model_loads = _named(spans, "agrag.embedding.model_load")
    assert len(model_loads) == 1, (
        f"expected one model_load across both calls, got {len(model_loads)}"
    )
    assert (model_loads[0].attributes or {}).get("agrag.model") == model
    assert len(_named(spans[:before_second], "agrag.embedding.model_load")) == 1, (
        "the single model_load must belong to the first call"
    )
    assert _named(spans[before_second:], "agrag.embedding.model_load") == [], (
        "a second call against the same instance must not reload the model"
    )


def _span_tree_path(name: str) -> Path:
    """Return the artifact path for the captured span tree."""
    root = Path(__file__).resolve().parents[3]
    directory = root / "reports" / "embedding"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / name


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


class TestEmbedderTracing:
    """Real embedders export one model-load span per instance lifetime."""

    @pytest.mark.skipif(embed_local_missing, reason="embed-local extra not installed")
    async def test_sentence_transformer_loads_model_once(self) -> None:
        """First embed exports model_load; second embed exports none."""
        provider, exporter = _tracing_provider()
        embedder = SentenceTransformerEmbedder(tracer=provider.get_tracer("agrag-test"))
        first = await embedder.embed(["first passage", "second passage"])
        before_second = len(exporter.get_finished_spans())
        second = await embedder.embed(["third passage"])
        assert len(first) == 2
        assert len(second) == 1
        dimension = len(first[0])
        assert dimension > 0
        for vector in (*first, *second):
            assert len(vector) == dimension

        spans = list(exporter.get_finished_spans())
        _assert_loads_once(spans, embedder.model, before_second=before_second)
        assert len(_named(spans, "agrag.embedding.encode")) == 2

        _write_span_tree(_span_tree_path("sentence_transformer_tracing.json"), spans)

    async def test_fastembed_bm25_loads_model_once(self) -> None:
        """First embed exports model_load; second embed exports none."""
        provider, exporter = _tracing_provider()
        embedder = FastEmbedBM25Embedder(tracer=provider.get_tracer("agrag-test"))
        first = await embedder.embed(["first passage", "second passage"])
        before_second = len(exporter.get_finished_spans())
        second = await embedder.embed(["third passage"])
        assert len(first) == 2
        assert len(second) == 1
        for vector in (*first, *second):
            assert len(vector.indices) == len(vector.values)
            assert len(vector.indices) > 0

        spans = list(exporter.get_finished_spans())
        _assert_loads_once(spans, embedder.model, before_second=before_second)
        assert len(_named(spans, "agrag.embedding.encode")) == 2

        _write_span_tree(_span_tree_path("fastembed_bm25_tracing.json"), spans)
