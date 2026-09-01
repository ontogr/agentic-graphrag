"""Tests for ChunkRetriever."""

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

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
