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

import pytest

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

    async def test_returns_empty_when_search_finds_nothing(self) -> None:
        """A search with no hits returns an empty list without a graph read."""
        gs = AsyncMock()

        with patch(
            "agrag.retrieval.retrievers.chunk.vector_search",
            new_callable=AsyncMock,
        ) as mock_vs:
            mock_vs.return_value = []
            results = await ChunkRetriever(
                graph_store=gs, embedder=MockEmbedder()
            ).retrieve("test")

        assert results == []
        gs.execute_read.assert_not_awaited()

    async def test_loading_query_failure_raises(self) -> None:
        """A loading query failure raises, so it is not read as no results."""
        gs = AsyncMock()
        gs.execute_read.side_effect = RuntimeError("db down")
        embedder = MockEmbedder()

        with patch(
            "agrag.retrieval.retrievers.chunk.vector_search",
            new_callable=AsyncMock,
        ) as mock_vs:
            mock_vs.return_value = [VectorHit(id=uuid4(), score=0.9, payload={})]

            retriever = ChunkRetriever(graph_store=gs, embedder=embedder)
            with pytest.raises(RuntimeError, match="db down"):
                await retriever.retrieve("test")

    async def test_unparsable_row_is_skipped(self) -> None:
        """A row that fails to parse is skipped; other rows still load."""
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
    """Properties required to load a chunk row."""

    document_id: str
    text: str
    provenance: str
    level: NotRequired[int]
    parent_id: NotRequired[str]


class _ChunkNode(TypedDict):
    """A graph node returned in a chunk loading row."""

    id: str
    properties: _ChunkProperties


class _ChunkRow(TypedDict):
    """A graph loading result containing one chunk node."""

    n: _ChunkNode


def _node(
    chunk_id: UUID,
    document_id: UUID,
    text: str,
    *,
    level: int = 0,
    parent_id: UUID | None = None,
) -> _ChunkRow:
    """Build a typed chunk loading row."""
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
