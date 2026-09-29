"""Tests for ChunkRetriever in agrag.retrieval.retrievers.chunk.

Patches ``agrag.retrieval.retrievers.chunk.vector_search`` with an AsyncMock
to control the returned VectorHits, and uses an AsyncMock graph store
returning raw node properties (including JSON-encoded provenance) to build
Chunk objects. Covers parsing a hit into a Chunk and skipping hits whose
node id is not found in the store.
"""

import json
from typing import NotRequired, TypedDict
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.vector_record import VectorHit
from agrag.retrieval.retrievers.chunk import ChunkRetriever


class MockEmbedder:
    """Mock embedder for chunk retriever tests."""

    async def embed_one(self, text: str) -> list[float]:
        """Method under test."""
        return [0.1, 0.2]


class TestChunkRetriever:
    """ChunkRetriever searches chunks via vector similarity."""

    async def test_returns_chunks(self) -> None:
        """Hits are parsed into Chunk objects."""
        ch_id = uuid4()
        doc_id = uuid4()
        gs = AsyncMock()
        gs.execute_read.return_value = [
            {
                "n": {
                    "id": str(ch_id),
                    "properties": {
                        "document_id": str(doc_id),
                        "index": 0,
                        "text": "Hello world",
                        "provenance": json.dumps(
                            {
                                "kind": "text",
                                "char_start": 0,
                                "char_end": 11,
                            }
                        ),
                        "heading_path": [],
                        "content_kind": "text",
                    },
                }
            }
        ]
        embedder = MockEmbedder()

        with patch(
            "agrag.retrieval.retrievers.chunk.vector_search",
            new_callable=AsyncMock,
        ) as mock_vs:
            mock_vs.return_value = [VectorHit(id=ch_id, score=0.85, payload={})]

            retriever = ChunkRetriever(graph_store=gs, embedder=embedder)
            results = await retriever.retrieve("test")

            assert len(results) == 1
            assert isinstance(results[0].item, Chunk)
            assert results[0].item.text == "Hello world"
            assert results[0].method == "chunk"

    async def test_reads_chunker_fields_from_node(self) -> None:
        """A chunk node with chunker properties returns them on the Chunk."""
        ch_id = uuid4()
        gs = AsyncMock()
        gs.execute_read.return_value = [
            {
                "n": {
                    "id": str(ch_id),
                    "properties": {
                        "document_id": str(uuid4()),
                        "text": "Hello world",
                        "provenance": json.dumps(
                            {"kind": "text", "char_start": 0, "char_end": 11}
                        ),
                        "chunker": "recursive",
                        "chunker_hash": "0123456789abcdef",
                    },
                }
            }
        ]

        with patch(
            "agrag.retrieval.retrievers.chunk.vector_search",
            new_callable=AsyncMock,
        ) as mock_vs:
            mock_vs.return_value = [VectorHit(id=ch_id, score=0.5, payload={})]
            results = await ChunkRetriever(
                graph_store=gs, embedder=MockEmbedder()
            ).retrieve("test")

        chunk = results[0].item
        assert isinstance(chunk, Chunk)
        assert chunk.chunker == "recursive"
        assert chunk.chunker_hash == "0123456789abcdef"

    async def test_legacy_node_has_no_chunker_fields(self) -> None:
        """A chunk node written before chunkers were recorded reads as None."""
        ch_id = uuid4()
        gs = AsyncMock()
        gs.execute_read.return_value = [
            {
                "n": {
                    "id": str(ch_id),
                    "properties": {
                        "document_id": str(uuid4()),
                        "text": "old",
                        "provenance": json.dumps(
                            {"kind": "text", "char_start": 0, "char_end": 3}
                        ),
                    },
                }
            }
        ]

        with patch(
            "agrag.retrieval.retrievers.chunk.vector_search",
            new_callable=AsyncMock,
        ) as mock_vs:
            mock_vs.return_value = [VectorHit(id=ch_id, score=0.5, payload={})]
            results = await ChunkRetriever(
                graph_store=gs, embedder=MockEmbedder()
            ).retrieve("test")

        chunk = results[0].item
        assert isinstance(chunk, Chunk)
        assert chunk.chunker is None
        assert chunk.chunker_hash is None

    async def test_skips_missing_chunks(self) -> None:
        """Chunks not found in the store are skipped."""
        gs = AsyncMock()
        gs.execute_read.return_value = []
        embedder = MockEmbedder()

        with patch(
            "agrag.retrieval.retrievers.chunk.vector_search",
            new_callable=AsyncMock,
        ) as mock_vs:
            mock_vs.return_value = [VectorHit(id=uuid4(), score=0.8, payload={})]

            retriever = ChunkRetriever(graph_store=gs, embedder=embedder)
            results = await retriever.retrieve("test")

            assert len(results) == 0

    async def test_hydration_query_raises_returns_empty(self) -> None:
        """A hydration query failure returns no results, not an exception."""
        gs = AsyncMock()
        gs.execute_read.side_effect = RuntimeError("db down")
        embedder = MockEmbedder()

        with patch(
            "agrag.retrieval.retrievers.chunk.vector_search",
            new_callable=AsyncMock,
        ) as mock_vs:
            mock_vs.return_value = [VectorHit(id=uuid4(), score=0.9, payload={})]

            retriever = ChunkRetriever(graph_store=gs, embedder=embedder)
            results = await retriever.retrieve("test")

            assert results == []

    async def test_unparsable_row_is_skipped(self) -> None:
        """A row that fails to parse is skipped; other rows still hydrate."""
        good_id = uuid4()
        doc_id = uuid4()
        bad_id = uuid4()
        gs = AsyncMock()
        gs.execute_read.return_value = [
            {"n": {"id": str(bad_id), "properties": {}}},
            {
                "n": {
                    "id": str(good_id),
                    "properties": {
                        "document_id": str(doc_id),
                        "index": 0,
                        "text": "Hello world",
                        "provenance": json.dumps(
                            {"kind": "text", "char_start": 0, "char_end": 11}
                        ),
                        "heading_path": [],
                        "content_kind": "text",
                    },
                }
            },
        ]
        embedder = MockEmbedder()

        with patch(
            "agrag.retrieval.retrievers.chunk.vector_search",
            new_callable=AsyncMock,
        ) as mock_vs:
            mock_vs.return_value = [
                VectorHit(id=bad_id, score=0.5, payload={}),
                VectorHit(id=good_id, score=0.9, payload={}),
            ]

            retriever = ChunkRetriever(graph_store=gs, embedder=embedder)
            results = await retriever.retrieve("test")

            assert len(results) == 1
            assert results[0].item.text == "Hello world"

    async def test_zero_limit_returns_empty_without_searching(self) -> None:
        """limit=0 returns no results and never reaches vector_search."""
        gs = AsyncMock()
        gs.execute_read.return_value = []
        embedder = MockEmbedder()

        with patch(
            "agrag.retrieval.retrievers.chunk.vector_search",
            new_callable=AsyncMock,
        ) as mock_vs:
            retriever = ChunkRetriever(graph_store=gs, embedder=embedder)
            results = await retriever.retrieve("test", limit=0)

            assert results == []
            mock_vs.assert_not_called()
            gs.execute_read.assert_not_called()


class _ChunkProperties(TypedDict):
    """Properties required to hydrate a chunk row."""

    document_id: str
    text: str
    provenance: str
    level: NotRequired[int]
    parent_id: NotRequired[str]


class _ChunkNode(TypedDict):
    """A graph node returned in a chunk hydration row."""

    id: str
    properties: _ChunkProperties


class _ChunkRow(TypedDict):
    """A graph hydration result containing one chunk node."""

    n: _ChunkNode


def _node(
    chunk_id: UUID,
    document_id: UUID,
    text: str,
    *,
    level: int = 0,
    parent_id: UUID | None = None,
) -> _ChunkRow:
    """Build a typed chunk hydration row."""
    properties: _ChunkProperties = {
        "document_id": str(document_id),
        "text": text,
        "provenance": json.dumps(
            {"kind": "text", "char_start": 0, "char_end": len(text)}
        ),
    }
    if level:
        properties["level"] = level
    if parent_id is not None:
        properties["parent_id"] = str(parent_id)
    return {"n": {"id": str(chunk_id), "properties": properties}}


class TestParentAttachment:
    """A child hit returns with its parent chunk attached."""

    def _store(self, nodes: dict[str, _ChunkRow], calls: list[list[str]]) -> AsyncMock:
        store = AsyncMock()

        async def read(query: str, params: dict[str, list[str]]) -> list[_ChunkRow]:
            calls.append(list(params["ids"]))
            return [nodes[i] for i in params["ids"] if i in nodes]

        store.execute_read.side_effect = read
        return store

    async def _retrieve(self, store: AsyncMock, hit_ids: list) -> list:
        with patch(
            "agrag.retrieval.retrievers.chunk.vector_search", new_callable=AsyncMock
        ) as search:
            search.return_value = [
                VectorHit(id=i, score=0.9 - n / 10, payload={})
                for n, i in enumerate(hit_ids)
            ]
            return await ChunkRetriever(
                graph_store=store, embedder=MockEmbedder()
            ).retrieve("q")

    async def test_attaches_the_parent_and_loads_a_shared_parent_once(self) -> None:
        """Two children of one parent cause one extra query for one parent id."""
        document_id, parent_id, first, second = uuid4(), uuid4(), uuid4(), uuid4()
        nodes = {
            str(parent_id): _node(parent_id, document_id, "the whole parent", level=1),
            str(first): _node(first, document_id, "child a", parent_id=parent_id),
            str(second): _node(second, document_id, "child b", parent_id=parent_id),
        }
        calls: list[list[str]] = []

        results = await self._retrieve(self._store(nodes, calls), [first, second])

        assert [r.item.text for r in results] == ["child a", "child b"]
        assert [r.parent.text for r in results] == ["the whole parent"] * 2
        assert calls == [[str(first), str(second)], [str(parent_id)]]

    async def test_chunk_without_a_parent_needs_no_second_query(self) -> None:
        """A standalone chunk has parent None and costs one query."""
        chunk_id, document_id = uuid4(), uuid4()
        nodes = {str(chunk_id): _node(chunk_id, document_id, "alone")}
        calls: list[list[str]] = []

        results = await self._retrieve(self._store(nodes, calls), [chunk_id])

        assert results[0].parent is None
        assert len(calls) == 1

    async def test_missing_or_closed_parent_omits_the_child(self) -> None:
        """A child result requires its parent chunk."""
        child, document_id = uuid4(), uuid4()
        nodes = {str(child): _node(child, document_id, "orphan", parent_id=uuid4())}

        results = await self._retrieve(self._store(nodes, []), [child])

        assert results == []

    async def test_parent_query_failure_omits_the_child_results(self) -> None:
        """A failed parent query omits child results without their context."""
        child, document_id, parent_id = uuid4(), uuid4(), uuid4()
        child_node = _node(child, document_id, "kept", parent_id=parent_id)
        store = AsyncMock()
        store.execute_read.side_effect = [[child_node], RuntimeError("down")]

        results = await self._retrieve(store, [child])

        assert results == []


class TestParentHydrationTracing:
    """Parent hydration records an observable best-effort fallback."""

    async def test_parent_query_failure_records_unset_hydration_span(self) -> None:
        """A failed parent read records its exception while returning the child."""
        provider = TracerProvider()
        exporter = InMemorySpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("test")
        child, document_id, parent_id = uuid4(), uuid4(), uuid4()
        child_node = _node(child, document_id, "kept", parent_id=parent_id)
        store = AsyncMock()
        store.execute_read.side_effect = [[child_node], RuntimeError("down")]

        with patch(
            "agrag.retrieval.retrievers.chunk.vector_search", new_callable=AsyncMock
        ) as search:
            search.return_value = [VectorHit(id=child, score=0.9, payload={})]
            with tracer.start_as_current_span("test.retrieve") as parent_span:
                results = await ChunkRetriever(
                    graph_store=store, embedder=MockEmbedder(), tracer=tracer
                ).retrieve("q")

        assert results == []
        (span,) = [
            span
            for span in exporter.get_finished_spans()
            if span.name == "agrag.retrieval.hydrate_parents"
        ]
        assert span.parent is not None
        assert span.parent.span_id == parent_span.get_span_context().span_id
        assert span.status.status_code is StatusCode.UNSET
        assert (span.attributes or {})["agrag.parent_count"] == 1
        assert len(list(span.events)) == 1

    async def test_parent_hydration_records_attached_parent_attributes(
        self,
    ) -> None:
        """A successful parent read records the context available to child results."""
        provider = TracerProvider()
        exporter = InMemorySpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("test")
        document_id, parent_id, child_id = uuid4(), uuid4(), uuid4()
        parent_node = _node(parent_id, document_id, "full context", level=1)
        child_node = _node(
            child_id, document_id, "matching detail", parent_id=parent_id
        )
        store = AsyncMock()
        store.execute_read.side_effect = [[child_node], [parent_node]]

        with patch(
            "agrag.retrieval.retrievers.chunk.vector_search", new_callable=AsyncMock
        ) as search:
            search.return_value = [VectorHit(id=child_id, score=0.9, payload={})]
            results = await ChunkRetriever(
                graph_store=store, embedder=MockEmbedder(), tracer=tracer
            ).retrieve("q")

        assert results[0].parent is not None
        (span,) = [
            span
            for span in exporter.get_finished_spans()
            if span.name == "agrag.retrieval.hydrate_parents"
        ]
        attributes = span.attributes or {}
        assert attributes["agrag.result.count"] == 1
        assert json.loads(attributes["retrieval.documents"]) == [
            {
                "document.id": str(parent_id),
                "document.content": "full context",
                "document.metadata": {
                    "document_id": str(document_id),
                    "level": 1,
                },
            }
        ]
