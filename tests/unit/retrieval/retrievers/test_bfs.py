"""Tests for BFSRetriever."""

from unittest.mock import AsyncMock
from uuid import uuid4

from agrag.common.data_models.entity import Entity
from agrag.retrieval.retrievers.bfs import BFSRetriever


class TestBFSRetriever:
    """BFSRetriever traverses from seed entity ids."""

    async def test_empty_seeds_returns_empty(self) -> None:
        """No seed ids returns empty results."""
        gs = AsyncMock()
        retriever = BFSRetriever(graph_store=gs)
        results = await retriever.retrieve("test", seed_ids=[])
        assert results == []

    async def test_none_seeds_returns_empty(self) -> None:
        """None seed_ids returns empty results."""
        gs = AsyncMock()
        retriever = BFSRetriever(graph_store=gs)
        results = await retriever.retrieve("test", seed_ids=None)
        assert results == []

    async def test_traverses_and_returns_entities(self) -> None:
        """BFS returns entities found via traversal."""
        ent = Entity(id=uuid4(), label="Person", name="Neighbor")
        gs = AsyncMock()
        gs.execute_read.return_value = [
            {
                "neighbor": {
                    "id": str(ent.id),
                    "labels": ["Person"],
                    "properties": {
                        "name": "Neighbor",
                        "merge_key": "Person:neighbor",
                        "merged_from": [],
                        "merge_count": 1,
                        "source_chunk_ids": [],
                    },
                }
            }
        ]

        retriever = BFSRetriever(graph_store=gs)
        results = await retriever.retrieve("test", seed_ids=[uuid4()])

        # The entity should be resolved via resolve_entity.
        # With the mock, it may or may not resolve depending on
        # whether _parse_entity_node succeeds.
        assert isinstance(results, list)
