"""Tests for EntityRetriever."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.vector_record import VectorHit
from agrag.retrieval.retrievers.entity import EntityRetriever


class MockEmbedder:
    """Mock embedder for entity retriever tests."""

    async def embed_one(self, text: str) -> list[float]:
        """Method under test."""
        return [0.1, 0.2]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Method under test."""
        return [[0.1, 0.2] for _ in texts]


class TestEntityRetriever:
    """EntityRetriever resolves hits through merged_into."""

    async def test_returns_resolved_entities(self) -> None:
        """Hits are resolved through resolve_entity and returned."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        gs = AsyncMock()
        embedder = MockEmbedder()

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

            retriever = EntityRetriever(graph_store=gs, embedder=embedder)
            results = await retriever.retrieve("test query")

            assert len(results) == 1
            assert results[0].item.id == ent.id
            assert results[0].method == "entity"

    async def test_skips_unresolvable_entities(self) -> None:
        """Entities that fail to resolve are skipped."""
        gs = AsyncMock()
        embedder = MockEmbedder()

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
            mock_vs.return_value = [VectorHit(id=uuid4(), score=0.9, payload={})]
            mock_resolve.side_effect = ValueError("not found")

            retriever = EntityRetriever(graph_store=gs, embedder=embedder)
            results = await retriever.retrieve("test query")

            assert len(results) == 0

    async def test_regression_returns_survivor_not_tombstone(
        self,
    ) -> None:
        """Regression: EntityRetriever returns survivor, not tombstone.

        When the store has a merged_into chain, the retriever must
        return the live survivor entity. This test fails without
        resolve_entity wired in correctly.
        """
        survivor = Entity(id=uuid4(), label="Person", name="Alice (survivor)")
        tombstone_id = uuid4()

        gs = AsyncMock()
        embedder = MockEmbedder()

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
            # The vector store returns the tombstone id.
            mock_vs.return_value = [VectorHit(id=tombstone_id, score=0.9, payload={})]
            # resolve_entity follows merged_into and returns survivor.
            mock_resolve.return_value = survivor

            retriever = EntityRetriever(graph_store=gs, embedder=embedder)
            results = await retriever.retrieve("test query")

            assert len(results) == 1
            assert results[0].item.id == survivor.id
            assert results[0].item.name == "Alice (survivor)"
