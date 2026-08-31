"""Tests for vector_search helper."""

from unittest.mock import AsyncMock
from uuid import uuid4

from agrag.common.data_models.vector_record import VectorHit
from agrag.retrieval.methods.vector import vector_search
from agrag.retrieval.settings import RetrievalSettings


class MockEmbedder:
    """Mock embedder for vector search tests."""

    async def embed_one(self, text: str) -> list[float]:
        """Method under test."""
        return [0.1, 0.2, 0.3]


class TestVectorSearch:
    """vector_search selects GraphStore or VectorStore path."""

    async def test_uses_graph_store_when_no_vector_store(self) -> None:
        """Without vector_store, calls graph_store.vector_search."""
        gs = AsyncMock()
        gs.vector_search.return_value = [VectorHit(id=uuid4(), score=0.9, payload={})]
        embedder = MockEmbedder()
        settings = RetrievalSettings()

        hits = await vector_search(
            "test query",
            embedder=embedder,
            graph_store=gs,
            vector_store=None,
            label_or_collection="Person",
            limit=10,
            filters=None,
            settings=settings,
        )

        gs.vector_search.assert_called_once()
        assert len(hits) == 1

    async def test_uses_vector_store_when_provided(self) -> None:
        """With vector_store, calls vector_store.hybrid_search."""
        gs = AsyncMock()
        vs = AsyncMock()
        vs.hybrid_search.return_value = [VectorHit(id=uuid4(), score=0.8, payload={})]
        embedder = MockEmbedder()
        settings = RetrievalSettings(hybrid_alpha=0.7)

        hits = await vector_search(
            "test query",
            embedder=embedder,
            graph_store=gs,
            vector_store=vs,
            label_or_collection="agrag_entities",
            limit=10,
            filters=None,
            settings=settings,
        )

        vs.hybrid_search.assert_called_once()
        gs.vector_search.assert_not_called()
        assert len(hits) == 1

    async def test_never_calls_both_stores(self) -> None:
        """Only one store is called, never both."""
        gs = AsyncMock()
        gs.vector_search.return_value = []
        vs = AsyncMock()
        vs.hybrid_search.return_value = []
        embedder = MockEmbedder()
        settings = RetrievalSettings()

        # With vector_store, only vs is called.
        await vector_search(
            "q",
            embedder=embedder,
            graph_store=gs,
            vector_store=vs,
            label_or_collection="col",
            limit=5,
            filters=None,
            settings=settings,
        )
        gs.vector_search.assert_not_called()
        vs.hybrid_search.assert_called_once()

        # Without vector_store, only gs is called.
        gs.reset_mock()
        vs.reset_mock()
        await vector_search(
            "q",
            embedder=embedder,
            graph_store=gs,
            vector_store=None,
            label_or_collection="Person",
            limit=5,
            filters=None,
            settings=settings,
        )
        gs.vector_search.assert_called_once()
        vs.hybrid_search.assert_not_called()
