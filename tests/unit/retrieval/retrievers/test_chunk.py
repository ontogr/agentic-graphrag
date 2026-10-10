"""Tests for ChunkRetriever in agrag.retrieval.retrievers.chunk.

Patches ``agrag.retrieval.retrievers.chunk.vector_search`` with an AsyncMock
to control the returned VectorHits, and uses an AsyncMock graph store
returning raw node properties (including JSON-encoded provenance) to build
Chunk objects. Covers skipping hits that are not chunks or are missing from
the store, skipping unparsable rows, and a failing loading query raising.
"""

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from agrag.common.data_models.vector_record import VectorHit
from agrag.retrieval.chunking import parse_chunk_node
from agrag.retrieval.retrievers.chunk import ChunkRetriever


class MockEmbedder:
    """Mock embedder for chunk retriever tests."""

    async def embed_one(self, text: str) -> list[float]:
        """Method under test."""
        return [0.1, 0.2]


class TestChunkRetriever:
    """ChunkRetriever searches chunks via vector similarity."""

    @pytest.mark.parametrize(
        "extra",
        [
            {"text": None},
            {"provenance": None},
        ],
        ids=["no-text", "no-provenance"],
    )
    def test_a_node_that_is_not_a_chunk_is_skipped(self, extra: dict) -> None:
        """Table, figure and bare nodes never become empty chunks."""
        node = {
            "id": str(uuid4()),
            "document_id": str(uuid4()),
            "text": "x",
            "provenance": json.dumps({"kind": "page", "page_spans": []}),
            **extra,
        }

        assert parse_chunk_node(node) is None

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
