"""Tests for required_member_ids threshold scoping."""

from uuid import uuid4

from agrag.common.data_models.community import Community
from agrag.ingestion.community import required_member_ids


class TestRequiredMemberIds:
    """required_member_ids respects thresholds."""

    def test_llm_qualifying_truncated(self) -> None:
        """LLM-qualifying community contributes top max_members_per_prompt ids."""
        eids = [uuid4() for _ in range(10)]
        comm = Community(
            id=uuid4(),
            title="",
            summary="",
            rating=0,
            rating_explanation="",
            member_ids=eids,
            internal_weight=10.0,
        )
        needed = required_member_ids(
            [comm], min_importance_for_llm_report=5.0, max_members_per_prompt=4
        )
        assert len(needed) == 4
        assert needed == set(eids[:4])

    def test_heuristic_contributes_top3(self) -> None:
        """Heuristic tier contributes only top 3."""
        eids = [uuid4() for _ in range(10)]
        comm = Community(
            id=uuid4(),
            title="",
            summary="",
            rating=0,
            rating_explanation="",
            member_ids=eids,
            internal_weight=1.0,
        )
        needed = required_member_ids(
            [comm], min_importance_for_llm_report=5.0, max_members_per_prompt=4
        )
        assert len(needed) == 3
        assert needed == set(eids[:3])
