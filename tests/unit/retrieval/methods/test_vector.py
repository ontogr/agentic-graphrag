"""Tests for vector_search helper."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from agrag.common.data_models.vector_record import VectorHit
from agrag.retrieval.filters import SearchFilters
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
            collection="agrag_entities",
            labels=["Person"],
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
            collection="agrag_entities",
            labels=["Person"],
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
            collection="col",
            labels=["Person"],
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
            collection="agrag_entities",
            labels=["Person"],
            limit=5,
            filters=None,
            settings=settings,
        )
        gs.vector_search.assert_called_once()
        vs.hybrid_search.assert_not_called()

    async def test_searches_every_label_index_natively(self) -> None:
        """Native search runs once per label and merges by score."""
        person_hit = VectorHit(id=uuid4(), score=0.4, payload={})
        drug_hit = VectorHit(id=uuid4(), score=0.9, payload={})
        gs = AsyncMock()
        gs.vector_search.side_effect = [[person_hit], [drug_hit]]

        hits = await vector_search(
            "q",
            embedder=MockEmbedder(),
            graph_store=gs,
            vector_store=None,
            collection="agrag_entities",
            labels=["Person", "Drug"],
            limit=10,
            filters=None,
            settings=RetrievalSettings(),
        )

        searched = [call.kwargs["label"] for call in gs.vector_search.call_args_list]
        assert searched == ["Person", "Drug"]
        assert [hit.id for hit in hits] == [drug_hit.id, person_hit.id]

    async def test_labels_are_not_sent_as_node_properties(self) -> None:
        """Native search filters on properties only, never on label."""
        gs = AsyncMock()
        gs.vector_search.return_value = []

        await vector_search(
            "q",
            embedder=MockEmbedder(),
            graph_store=gs,
            vector_store=None,
            collection="agrag_entities",
            labels=["Person"],
            limit=10,
            filters=SearchFilters(labels=["Person"], properties={"status": "active"}),
            settings=RetrievalSettings(),
        )

        assert gs.vector_search.call_args.kwargs["filters"] == {"status": "active"}

    async def test_native_search_without_labels_raises(self) -> None:
        """Native search with no label to search is a configuration error."""
        gs = AsyncMock()

        with pytest.raises(ValueError, match="at least one label"):
            await vector_search(
                "q",
                embedder=MockEmbedder(),
                graph_store=gs,
                vector_store=None,
                collection="agrag_entities",
                labels=[],
                limit=10,
                filters=None,
                settings=RetrievalSettings(),
            )
