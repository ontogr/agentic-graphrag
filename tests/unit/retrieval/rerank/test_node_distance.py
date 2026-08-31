"""Tests for node_distance_rerank."""

from uuid import uuid4

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.search_result import SearchResult
from agrag.retrieval.rerank.node_distance import node_distance_rerank


class MockGraphStore:
    """Mock graph store for distance reranker tests."""

    def __init__(self, distances: dict | None = None) -> None:
        """Method under test."""
        self._distances = distances or {}

    async def execute_read(self, query: str, params: dict) -> list:
        """Method under test."""
        if "shortestPath" in query:
            target = params.get("target_id")
            dist = self._distances.get(target, 999999.0)
            return [{"dist": dist}]
        return []


class TestNodeDistanceRerank:
    """node_distance_rerank reorders by graph proximity."""

    async def test_empty_input(self) -> None:
        """Empty results return empty."""
        result = await node_distance_rerank(
            [], graph_store=MockGraphStore(), seed_ids=[]
        )
        assert result == []

    async def test_no_seeds(self) -> None:
        """No seeds returns results unchanged."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        r = SearchResult(item=ent, score=1.0, method="test")
        result = await node_distance_rerank(
            [r], graph_store=MockGraphStore(), seed_ids=[]
        )
        assert len(result) == 1

    async def test_closer_entities_rank_higher(self) -> None:
        """Entities closer to seeds rank higher."""
        close_id = uuid4()
        far_id = uuid4()
        seed_id = uuid4()

        close_ent = Entity(id=close_id, label="Person", name="Close")
        far_ent = Entity(id=far_id, label="Person", name="Far")
        r_close = SearchResult(item=close_ent, score=0.5, method="test")
        r_far = SearchResult(item=far_ent, score=0.9, method="test")

        store = MockGraphStore({str(close_id): 1.0, str(far_id): 5.0})
        result = await node_distance_rerank(
            [r_far, r_close],
            graph_store=store,
            seed_ids=[seed_id],
        )
        assert result[0].item.id == close_id
        assert result[1].item.id == far_id
