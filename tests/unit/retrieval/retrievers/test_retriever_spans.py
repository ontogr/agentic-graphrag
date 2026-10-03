"""Tests for the retriever spans.

Each retriever exports one ``RETRIEVER`` span with ``input.value`` equal to
the query and results matching what it returned; its stage and helper spans
nest under it. Swallow sites record an exception event and leave the span
status UNSET. Stores are mocks at the driver boundary; the real vector_search
runs against them, so the exported spans are the real ones.
"""

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_schema import GENERIC
from agrag.common.data_models.search_result import SearchResult
from agrag.common.data_models.vector_record import VectorHit
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.retrievers import text2cypher as t2c_module
from agrag.retrieval.retrievers.bfs import BFSRetriever
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


def _entity_node(entity_id) -> dict:
    """Return one stored entity node."""
    return {
        "id": str(entity_id),
        "name": "Alice",
        "merge_key": "Person:alice",
        "merge_count": 1,
        "source_chunk_ids": [],
    }


def _entity_rows(entity_id) -> list[dict]:
    """Return one load_entities row."""
    return [{"n": _entity_node(entity_id)}]


def _chunk_rows(chunk_id) -> list[dict]:
    """Return one load_chunks row."""
    return [
        {
            "n": {
                "id": str(chunk_id),
                "labels": ["Chunk"],
                "properties": {
                    "document_id": str(uuid4()),
                    "index": 0,
                    "text": "a passage",
                    "provenance": json.dumps(
                        {"kind": "text", "char_start": 0, "char_end": 9}
                    ),
                },
            }
        }
    ]


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
    """ChunkRetriever's span tree and its loading swallow site."""

    async def test_exports_a_retriever_span_with_results(self) -> None:
        """The chunk span carries the kind, the query and the results."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        hits = [VectorHit(id=uuid4(), score=0.9, payload={})]
        store = _vector_searching_store(hits)
        store.execute_read.return_value = _chunk_rows(hits[0].id)
        retriever = ChunkRetriever(
            graph_store=store,
            embedder=_MockEmbedder(),
            settings=RetrievalSettings(),
            tracer=tracer,
        )

        results = await retriever.retrieve("find the passage")

        spans = exporter.get_finished_spans()
        chunk_spans = _named(spans, "agrag.retrieval.chunk")
        assert len(chunk_spans) == 1
        attributes = chunk_spans[0].attributes
        assert attributes is not None
        assert attributes["openinference.span.kind"] == "RETRIEVER"
        assert attributes["input.value"] == "find the passage"
        assert attributes["agrag.query"] == "find the passage"
        assert list(attributes["agrag.result_ids"]) == [
            str(result.item.id) for result in results
        ]
        assert len(attributes["agrag.result_texts"]) == len(results)
        # The vector search and loading spans nest under the chunk span.
        child_names = {
            span.name
            for span in spans
            if span.parent is not None
            and span.parent.span_id == chunk_spans[0].context.span_id
        }
        assert "agrag.retrieval.vector_search" in child_names
        assert "agrag.retrieval.load_chunks" in child_names
        load = _named(spans, "agrag.retrieval.load_chunks")[0]
        load_attributes = load.attributes
        assert load_attributes is not None
        assert load_attributes["agrag.requested_count"] == 1
        assert load_attributes["agrag.loaded_count"] == 1

    async def test_a_failing_loading_read_records_and_stays_unset(self) -> None:
        """A loading failure returns [] and records on load_chunks."""
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

        results = await retriever.retrieve("q")

        assert results == []
        spans = exporter.get_finished_spans()
        load = _named(spans, "agrag.retrieval.load_chunks")
        assert len(load) == 1
        assert [e for e in load[0].events if e.name == "exception"]
        assert load[0].status.status_code.name != "ERROR"
        chunk_span = _named(spans, "agrag.retrieval.chunk")[0]
        assert chunk_span.status.status_code.name != "ERROR"
        chunk_attributes = chunk_span.attributes
        assert chunk_attributes is not None
        assert chunk_attributes["agrag.result_count"] == 0

    async def test_tracer_none_leaves_the_host_span_untouched(self) -> None:
        """An untraced retriever opens nothing and marks no host span."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        store = _vector_searching_store([VectorHit(id=uuid4(), score=0.9, payload={})])
        store.execute_read.return_value = []
        retriever = ChunkRetriever(
            graph_store=store,
            embedder=_MockEmbedder(),
            settings=RetrievalSettings(),
            tracer=None,
        )

        with tracer.start_as_current_span("host"):
            await retriever.retrieve("q")

        host = _named(exporter.get_finished_spans(), "host")[0]
        assert host.status.status_code.name != "ERROR"
        assert not [e for e in host.events if e.name == "exception"]


class TestBFSRetrieverSpan:
    """BFSRetriever's span tree."""

    async def test_exports_a_bfs_span_with_seed_attributes(self) -> None:
        """The bfs span carries seed count, depth and direction."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        store = AsyncMock()
        seed_id = uuid4()
        neighbor_id = uuid4()
        bfs_rows = [{"neighbor": _entity_node(neighbor_id), "id": str(neighbor_id)}]
        store.execute_read.return_value = bfs_rows
        retriever = BFSRetriever(
            graph_store=store, settings=RetrievalSettings(), tracer=tracer
        )

        results = await retriever.retrieve(
            "", seed_ids=[seed_id], depth=2, direction="outgoing"
        )

        spans = exporter.get_finished_spans()
        bfs_spans = _named(spans, "agrag.retrieval.bfs")
        assert len(bfs_spans) == 1
        attributes = bfs_spans[0].attributes
        assert attributes is not None
        assert attributes["openinference.span.kind"] == "RETRIEVER"
        assert attributes["agrag.seed_count"] == 1
        assert attributes["agrag.depth"] == 2
        assert attributes["agrag.direction"] == "outgoing"
        assert list(attributes["agrag.result_ids"]) == [
            str(result.item.id) for result in results
        ]
        assert len(results) == 1

    async def test_no_seeds_records_empty_results(self) -> None:
        """A BFS with no seeds returns [] under a span with results."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        retriever = BFSRetriever(
            graph_store=AsyncMock(), settings=RetrievalSettings(), tracer=tracer
        )

        results = await retriever.retrieve("", seed_ids=None)

        assert results == []
        attributes = _named(exporter.get_finished_spans(), "agrag.retrieval.bfs")[
            0
        ].attributes
        assert attributes is not None
        assert attributes["agrag.result_count"] == 0


class TestEntityRetrieverSpans:
    """EntityRetriever's phase spans under a document scope."""

    async def test_document_scope_exports_the_phase_spans(self) -> None:
        """A scoped search shows allowed ids, both phases and the passes."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        hit_id = uuid4()
        entity_id = uuid4()
        hits = [VectorHit(id=hit_id, score=0.9, payload={})]
        store = _vector_searching_store(hits)

        async def _read(query, params=None, **kwargs):
            if "Document" in query:
                return [{"id": str(hit_id)}]
            if "ResolvedEntity" in query:
                return [
                    {
                        "resolved": {
                            "id": str(entity_id),
                            "name": "Alice",
                            "label": "Person",
                            "member_ids": [str(hit_id)],
                        }
                    }
                ]
            return _entity_rows(hit_id)

        store.execute_read.side_effect = _read
        retriever = EntityRetriever(
            graph_store=store,
            embedder=_MockEmbedder(),
            settings=RetrievalSettings(),
            entity_labels=["Person"],
            tracer=tracer,
        )

        results = await retriever.retrieve(
            "q", filters=SearchFilters(document_ids=["d1"])
        )

        spans = exporter.get_finished_spans()
        entity_attributes = _named(spans, "agrag.retrieval.entity")[0].attributes
        assert entity_attributes is not None
        assert list(entity_attributes["agrag.result_ids"]) == [
            str(result.item.id) for result in results
        ]
        allowed = _named(spans, "agrag.retrieval.allowed_entity_ids")
        assert len(allowed) == 1
        allowed_attributes = allowed[0].attributes
        assert allowed_attributes is not None
        assert allowed_attributes["agrag.document_count"] == 1
        assert allowed_attributes["agrag.entity_count"] == 1
        for name in (
            "agrag.retrieval.entity_search",
            "agrag.retrieval.resolved_entity_search",
        ):
            phase = _named(spans, name)
            assert len(phase) == 1, name
            phase_attributes = phase[0].attributes
            assert phase_attributes is not None
            assert phase_attributes["agrag.passes"] == 1
        searches = _named(spans, "agrag.retrieval.vector_search")
        assert len(searches) == 2

    async def test_a_failing_loading_read_marks_the_span_as_error(self) -> None:
        """A failed entity read propagates and sets the retrieval span to ERROR."""
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
        assert entity_span.status.status_code.name == "ERROR"

    async def test_tracer_none_leaves_the_host_span_untouched(self) -> None:
        """An untraced EntityRetriever marks no host span."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        store = _vector_searching_store([])
        retriever = EntityRetriever(
            graph_store=store,
            embedder=_MockEmbedder(),
            settings=RetrievalSettings(),
            entity_labels=["Person"],
            tracer=None,
        )

        with tracer.start_as_current_span("host"):
            await retriever.retrieve("q")

        host = _named(exporter.get_finished_spans(), "host")[0]
        assert host.status.status_code.name != "ERROR"
        assert not [e for e in host.events if e.name == "exception"]


class TestText2CypherSpans:
    """Text2CypherRetriever's execute_cypher spans."""

    async def test_a_repair_shows_two_execute_spans(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed first query and a repaired second export two spans."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        store = AsyncMock()
        calls = {"explain": 0}
        entity_id = uuid4()

        async def _read(query, params=None, **kwargs):
            if query.startswith("EXPLAIN"):
                calls["explain"] += 1
                if calls["explain"] == 1:
                    raise RuntimeError("plan failed")
                return []
            return [{"n": _entity_node(entity_id)}]

        store.execute_read.side_effect = _read

        async def _generate(self, question, *, failure_context=None):
            return "MATCH (n) WHERE n._pending_job_id IS NULL RETURN n"

        monkeypatch.setattr(
            t2c_module.Text2CypherRetriever, "_generate_cypher", _generate
        )
        retriever = Text2CypherRetriever(
            graph_store=store,
            schema=GENERIC,
            settings=RetrievalSettings(),
            tracer=tracer,
        )

        results = await retriever.retrieve("who knows alice")

        spans = exporter.get_finished_spans()
        executes = _named(spans, "agrag.retrieval.execute_cypher")
        assert len(executes) == 2
        attributes = [span.attributes for span in executes]
        first_attributes = attributes[0]
        second_attributes = attributes[1]
        assert first_attributes is not None
        assert second_attributes is not None
        assert first_attributes["agrag.is_repair"] is False
        assert second_attributes["agrag.is_repair"] is True
        assert int(second_attributes["agrag.row_count"]) >= 1  # type: ignore[call-overload]
        t2c_span = _named(spans, "agrag.retrieval.text2cypher")[0]
        t2c_attributes = t2c_span.attributes
        assert t2c_attributes is not None
        assert (
            t2c_attributes["agrag.cypher"]
            == "MATCH (n) WHERE n._pending_job_id IS NULL RETURN n"
        )
        assert list(t2c_attributes["agrag.result_ids"]) == [
            str(result.item.id) for result in results
        ]

    async def test_entity_row_loading_exports_its_own_span(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Loading an entity row exports a load_entities span with counts."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        store = AsyncMock()
        entity_id = uuid4()

        async def _read(query, params=None, **kwargs):
            if query.startswith("EXPLAIN"):
                return []
            return [{"n": _entity_node(entity_id)}]

        store.execute_read.side_effect = _read

        async def _generate(self, question, *, failure_context=None):
            return "MATCH (n) WHERE n._pending_job_id IS NULL RETURN n"

        monkeypatch.setattr(
            t2c_module.Text2CypherRetriever, "_generate_cypher", _generate
        )
        retriever = Text2CypherRetriever(
            graph_store=store,
            schema=GENERIC,
            settings=RetrievalSettings(),
            tracer=tracer,
        )

        await retriever.retrieve("who knows alice")

        loads = _named(exporter.get_finished_spans(), "agrag.graphdb.load_entities")
        assert len(loads) == 1
        attributes = loads[0].attributes
        assert attributes is not None
        assert attributes["agrag.requested_count"] == 1
        assert attributes["agrag.loaded_count"] == 1

    async def test_a_failed_generation_records_and_stays_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A generation failure records on the text2cypher span."""
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

        results = await retriever.retrieve("q")

        assert results == []
        t2c_span = _named(exporter.get_finished_spans(), "agrag.retrieval.text2cypher")[
            0
        ]
        assert [e for e in t2c_span.events if e.name == "exception"]
        assert t2c_span.status.status_code.name != "ERROR"


class TestEntityResultShape:
    """The result shape every retriever records."""

    def test_entity_result_is_a_search_result(self) -> None:
        """The test helpers build real SearchResults."""
        result = SearchResult(
            item=Entity(id=uuid4(), label="Person", name="Alice"),
            score=1.0,
            method="entity",
        )
        assert result.item.id is not None
