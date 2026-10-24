"""Tests for the retrieval helper spans.

Pins the span names and attributes of ``vector_search``. Runs real spans
through an in-memory exporter; stores are mocks at the driver boundary.
"""

import json
from unittest.mock import AsyncMock
from uuid import uuid4

from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.common.data_models.vector_record import VectorHit
from agrag.retrieval.methods.vector import vector_search


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Return a provider and exporter pair backed by one in-memory exporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _named(spans: tuple[ReadableSpan, ...], name: str) -> list[ReadableSpan]:
    """Return the exported spans whose name matches."""
    return [span for span in spans if span.name == name]


class _MockEmbedder:
    """Mock embedder for vector search tests."""

    async def embed_one(self, text: str) -> list[float]:
        """Return a fixed vector."""
        return [0.1, 0.2, 0.3]


class TestVectorSearchSpan:
    """vector_search records its labels, limit, and hits."""

    async def test_native_path_records_graph_native_and_hits(self) -> None:
        """The search records the labels, limit, and hit ids and scores."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        hit_a = VectorHit(id=uuid4(), score=0.9, payload={})
        hit_b = VectorHit(id=uuid4(), score=0.4, payload={})
        gs = AsyncMock()
        gs.vector_search.side_effect = [[hit_b], [hit_a]]

        hits = await vector_search(
            "q",
            embedder=_MockEmbedder(),
            graph_store=gs,
            labels=["Person", "Drug"],
            limit=10,
            filters=None,
            tracer=tracer,
        )

        spans = _named(exporter.get_finished_spans(), "agrag.retrieval.vector_search")
        assert len(spans) == 1
        attributes = spans[0].attributes
        assert attributes is not None
        assert list(attributes["agrag.labels"]) == ["Person", "Drug"]
        assert attributes["agrag.limit"] == 10
        assert json.loads(attributes["agrag.filters"]) == {
            "labels": [],
            "relation_types": [],
            "document_ids": [],
            "properties": {},
        }
        assert attributes["agrag.hit_count"] == 2
        assert list(attributes["agrag.hit_ids"]) == [str(hits[0].id), str(hits[1].id)]
        assert list(attributes["agrag.hit_scores"]) == [0.9, 0.4]
