"""Tests for the heuristic community report."""

from uuid import uuid4

from agrag.common.data_models.community import Community
from agrag.common.data_models.entity import Entity
from agrag.ingestion.community import _apply_heuristic_report


class TestHeuristicReport:
    """Heuristic report rating and names reflect internal_weight and centrality."""

    def test_heuristic_rating_and_names(self) -> None:
        """Rating is internal_weight/2 capped at 10; names are centrality ordered."""
        e1 = Entity(id=uuid4(), label="Person", name="Alice", properties={})
        e2 = Entity(id=uuid4(), label="Person", name="Bob", properties={})
        comm = Community(
            id=uuid4(),
            title="",
            summary="",
            rating=0,
            rating_explanation="",
            member_ids=[e1.id, e2.id],
            internal_weight=4.0,
        )
        _apply_heuristic_report(comm, {e1.id: e1, e2.id: e2})
        assert comm.rating == 2.0
        assert "Alice" in comm.title
