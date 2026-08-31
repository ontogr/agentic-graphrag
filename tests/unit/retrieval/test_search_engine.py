"""Tests for SearchEngine."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.vector_record import VectorHit
from agrag.retrieval.recipes import ENTITY, HYBRID
from agrag.retrieval.search_engine import SearchEngine


class MockEmbedder:
    """Mock embedder for search engine tests."""

    async def embed_one(self, text: str) -> list[float]:
        """Return a mock vector."""
        return [0.1, 0.2]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return mock vectors for a batch."""
        return [[0.1, 0.2] for _ in texts]


class TestSearchEngine:
    """SearchEngine fans out methods, fuses, and reranks."""

    async def test_single_method_search(self) -> None:
        """A single-method recipe runs one retriever."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        gs = AsyncMock()
        embedder = MockEmbedder()
        engine = SearchEngine(graph_store=gs, embedder=embedder)

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_vs,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_resolve,
        ):
            mock_vs.return_value = [VectorHit(id=ent.id, score=0.9, payload={})]
            mock_resolve.return_value = ent

            results = await engine.search("test", ENTITY)

            assert len(results) == 1
            assert results[0].item.id == ent.id

    async def test_hybrid_fuses_entity_and_chunk(self) -> None:
        """HYBRID recipe fuses entity and chunk results."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        ch = Chunk(
            id=uuid4(),
            document_id=uuid4(),
            index=0,
            text="Some text",
            provenance=TextProvenance(char_start=0, char_end=9),
        )

        gs = AsyncMock()
        embedder = MockEmbedder()
        engine = SearchEngine(graph_store=gs, embedder=embedder)

        with (
            patch(
                "agrag.retrieval.retrievers.entity.vector_search",
                new_callable=AsyncMock,
            ) as mock_ev,
            patch(
                "agrag.retrieval.retrievers.entity.resolve_entity",
                new_callable=AsyncMock,
            ) as mock_er,
            patch(
                "agrag.retrieval.retrievers.chunk.vector_search",
                new_callable=AsyncMock,
            ) as mock_cv,
            patch(
                "agrag.retrieval.retrievers.chunk.ChunkRetriever._parse_chunk_node",
            ) as mock_cp,
        ):
            mock_ev.return_value = [VectorHit(id=ent.id, score=0.9, payload={})]
            mock_er.return_value = ent
            mock_cv.return_value = [VectorHit(id=ch.id, score=0.8, payload={})]
            mock_cp.return_value = ch

            gs.execute_read.return_value = [
                {
                    "n": {
                        "id": str(ch.id),
                        "properties": {
                            "document_id": str(ch.document_id),
                            "index": 0,
                            "text": "Some text",
                            "provenance": '{"kind":"text","char_start":0,"char_end":9}',
                            "heading_path": [],
                            "content_kind": "text",
                        },
                    }
                }
            ]

            results = await engine.search("test", HYBRID)

            assert len(results) >= 1
