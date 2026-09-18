"""Tests for node_distance_rerank in agrag.retrieval.rerank.node_distance.

Uses a MockGraphStore whose execute_read returns a preset shortest-path
distance per target id, so no real Neo4j query runs. Covers empty input,
no seed ids leaving results unchanged, and that entities closer to the seed
set rank ahead of farther ones.
"""

from uuid import uuid4

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.resolved_entity import ResolvedEntity
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
            return [
                {"dist": self._distances.get(target, 999999.0)}
                for target in params.get("target_ids", [])
            ]
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

    async def test_resolved_entity_measured_by_closest_member(self) -> None:
        """A ResolvedEntity is scored by its nearest raw member, not skipped."""
        near_member = uuid4()
        far_member = uuid4()
        seed_id = uuid4()
        other_ent = Entity(id=uuid4(), label="Person", name="Other")
        resolved = ResolvedEntity(
            id=uuid4(),
            label="Person",
            name="Cluster",
            member_ids=[far_member, near_member],
        )
        r_resolved = SearchResult(item=resolved, score=0.5, method="test")
        r_other = SearchResult(item=other_ent, score=0.9, method="test")

        store = MockGraphStore({str(near_member): 1.0, str(other_ent.id): 5.0})
        result = await node_distance_rerank(
            [r_other, r_resolved],
            graph_store=store,
            seed_ids=[seed_id],
        )
        assert result[0].item is resolved
        assert result[1].item is other_ent
