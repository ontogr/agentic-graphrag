"""Tests for the retriever spans.

A failing retriever raises, records an exception event on its span, and marks
the span status ERROR. Stores are mocks at the driver boundary; the real
vector_search runs against them, so the exported spans are the real ones.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.common.data_models.graph_schema import GENERIC
from agrag.common.data_models.vector_record import VectorHit
from agrag.retrieval.retrievers import text2cypher as t2c_module
from agrag.retrieval.retrievers.chunk import ChunkRetriever
from agrag.retrieval.retrievers.entity import EntityRetriever
from agrag.retrieval.retrievers.text2cypher import Text2CypherRetriever
from agrag.retrieval.settings import RetrievalSettings


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
    """Mock embedder returning a fixed vector."""

    async def embed_one(self, text: str) -> list[float]:
        """Return a fixed vector."""
        return [0.1, 0.2, 0.3]


def _vector_searching_store(hits: list[VectorHit]) -> AsyncMock:
    """Return a store whose native vector search returns ``hits``."""
    store = AsyncMock()
    store.vector_search.return_value = hits
    return store


class TestChunkRetrieverSpan:
    """A failing ChunkRetriever loading read marks its spans as errors."""

    async def test_a_failing_loading_read_marks_the_spans_error(self) -> None:
        """A loading failure raises and marks load_chunks and the root ERROR."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        store = _vector_searching_store([VectorHit(id=uuid4(), score=0.9, payload={})])
        store.execute_read.side_effect = RuntimeError("read failed")
        retriever = ChunkRetriever(
            graph_store=store,
            embedder=_MockEmbedder(),
            settings=RetrievalSettings(),
            tracer=tracer,
        )

        with pytest.raises(RuntimeError, match="read failed"):
            await retriever.retrieve("q")

        spans = exporter.get_finished_spans()
        load = _named(spans, "agrag.retrieval.load_chunks")
        assert len(load) == 1
        assert [e.name for e in load[0].events] == ["exception"]
        assert load[0].status.status_code.name == "ERROR"
        chunk_span = _named(spans, "agrag.retrieval.chunk")[0]
        assert chunk_span.status.status_code.name == "ERROR"


class TestEntityRetrieverSpans:
    """EntityRetriever's phase spans under a document scope."""

    async def test_a_failing_loading_read_marks_the_span_error(self) -> None:
        """A failed entity read raises and marks the entity span ERROR."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        hits = [VectorHit(id=uuid4(), score=0.9, payload={})]
        store = _vector_searching_store(hits)

        async def _read(query, params=None, **kwargs):
            if "ResolvedEntity" in query or "MATCHES" in query:
                return []
            raise RuntimeError("read failed")

        store.execute_read.side_effect = _read
        retriever = EntityRetriever(
            graph_store=store,
            embedder=_MockEmbedder(),
            settings=RetrievalSettings(),
            entity_labels=["Person"],
            tracer=tracer,
        )

        with pytest.raises(RuntimeError, match="read failed"):
            await retriever.retrieve("q")

        entity_span = _named(exporter.get_finished_spans(), "agrag.retrieval.entity")[0]
        assert [e for e in entity_span.events if e.name == "exception"]
        assert entity_span.status.status_code.name == "ERROR"


class TestText2CypherSpans:
    """Text2CypherRetriever's execute_cypher spans."""

    async def test_a_failed_generation_marks_the_span_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A generation failure raises and marks the text2cypher span ERROR."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")

        async def _generate(self, question, *, failure_context=None):
            raise RuntimeError("no baml client")

        monkeypatch.setattr(
            t2c_module.Text2CypherRetriever, "_generate_cypher", _generate
        )
        retriever = Text2CypherRetriever(
            graph_store=AsyncMock(),
            schema=GENERIC,
            settings=RetrievalSettings(),
            tracer=tracer,
        )

        with pytest.raises(RuntimeError, match="no baml client"):
            await retriever.retrieve("q")

        t2c_span = _named(exporter.get_finished_spans(), "agrag.retrieval.text2cypher")[
            0
        ]
        assert [e for e in t2c_span.events if e.name == "exception"]
        assert t2c_span.status.status_code.name == "ERROR"
