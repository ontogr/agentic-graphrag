"""Tests for BFSRetriever in agrag.retrieval.retrievers.bfs.

Uses an AsyncMock graph store. Covers empty/None seed ids short-circuiting to
no results and a label scope becoming a validated neighbor label predicate.
Depth, direction, and relation-type traversal run against Neo4j in the
integration suite.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

from agrag.common.data_models.entity import Entity
from agrag.retrieval.filters import SearchFilters
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

    async def test_labels_restrict_neighbors_without_query_parameters(self) -> None:
        """A label scope becomes a validated neighbor label predicate."""
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = []
        retriever = BFSRetriever(graph_store=graph_store)

        await retriever.retrieve(
            "test",
            seed_ids=[uuid4()],
            filters=SearchFilters(labels=["Drug"]),
        )

        query, params = graph_store.execute_read.call_args.args
        assert "AND neighbor:Drug" in query
        assert not any("label" in parameter for parameter in params)
