"""Tests for generate_community_reports batching and fallbacks."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from agrag.common.data_models.community import Community
from agrag.common.data_models.entity import Entity
from agrag.ingestion.community import generate_community_reports


class TestGenerateCommunityReports:
    """Batched LLM reports with heuristic fallback."""

    async def test_heuristic_below_threshold_no_baml(self) -> None:
        """Below threshold uses heuristic with zero BAML calls."""
        eids = [uuid4() for _ in range(2)]
        entities_by_id = {
            eid: Entity(id=eid, label="Person", name=f"N{i}", properties={})
            for i, eid in enumerate(eids)
        }
        comm = Community(
            id=uuid4(),
            title="",
            summary="",
            rating=0,
            rating_explanation="",
            member_ids=eids,
            internal_weight=1.0,
        )
        with patch("agrag.llm.baml_client.b") as mock_b:
            mock_b.SummarizeCommunities = AsyncMock()
            failures = await generate_community_reports(
                [comm], entities_by_id, min_importance_for_llm_report=5.0
            )
            assert failures == []
            assert comm.title  # heuristic filled
            mock_b.SummarizeCommunities.assert_not_called()

    async def test_batched_and_truncated(self) -> None:
        """Qualifying communities batched and truncated to max_members_per_prompt."""
        eids = [uuid4() for _ in range(10)]
        entities_by_id = {
            eid: Entity(id=eid, label="Person", name=f"N{i}", properties={})
            for i, eid in enumerate(eids)
        }
        c1 = Community(
            id=uuid4(),
            title="",
            summary="",
            rating=0,
            rating_explanation="",
            member_ids=eids[:5],
            internal_weight=10.0,
        )
        c2 = Community(
            id=uuid4(),
            title="",
            summary="",
            rating=0,
            rating_explanation="",
            member_ids=eids[5:],
            internal_weight=10.0,
        )
        with patch("agrag.llm.baml_client.b") as mock_b:
            mock_b.SummarizeCommunities = AsyncMock(
                return_value=[
                    MagicMock(
                        title="T1",
                        summary="S1",
                        rating=8,
                        rating_explanation="e",
                        findings=[],
                    ),
                    MagicMock(
                        title="T2",
                        summary="S2",
                        rating=7,
                        rating_explanation="e",
                        findings=[],
                    ),
                ]
            )
            failures = await generate_community_reports(
                [c1, c2], entities_by_id, batch_size=2, max_members_per_prompt=2
            )
            assert len(failures) == 0
            assert c1.title == "T1"
            # Verify truncation: capture inputs
            captured = {}

            async def capture(communities):
                captured["inputs"] = communities
                return [
                    MagicMock(
                        title="T",
                        summary="S",
                        rating=5,
                        rating_explanation="e",
                        findings=[],
                    )
                ]

            mock_b.SummarizeCommunities = capture
            c_big = Community(
                id=uuid4(),
                title="",
                summary="",
                rating=0,
                rating_explanation="",
                member_ids=eids,
                internal_weight=10.0,
            )
            await generate_community_reports(
                [c_big], entities_by_id, max_members_per_prompt=3
            )
            assert len(captured["inputs"][0].entity_summaries) == 3

    async def test_batch_failure_falls_back(self) -> None:
        """Batch failure records StageFailure per community and falls back."""
        eids = [uuid4() for _ in range(2)]
        entities_by_id = {
            eid: Entity(id=eid, label="Person", name=f"N{i}", properties={})
            for i, eid in enumerate(eids)
        }
        c1 = Community(
            id=uuid4(),
            title="",
            summary="",
            rating=0,
            rating_explanation="",
            member_ids=eids,
            internal_weight=10.0,
        )
        with patch("agrag.llm.baml_client.b") as mock_b:
            mock_b.SummarizeCommunities = AsyncMock(side_effect=Exception("down"))
            failures = await generate_community_reports([c1], entities_by_id)
            assert len(failures) == 1
            assert c1.title  # heuristic fallback

    async def test_short_batch_response_fallback(self) -> None:
        """Short batch response falls back only for leftover communities."""
        eids = [uuid4() for _ in range(4)]
        entities_by_id = {
            eid: Entity(id=eid, label="Person", name=f"N{i}", properties={})
            for i, eid in enumerate(eids)
        }
        c1 = Community(
            id=uuid4(),
            title="",
            summary="",
            rating=0,
            rating_explanation="",
            member_ids=eids[:2],
            internal_weight=10.0,
        )
        c2 = Community(
            id=uuid4(),
            title="",
            summary="",
            rating=0,
            rating_explanation="",
            member_ids=eids[2:],
            internal_weight=10.0,
        )
        with patch("agrag.llm.baml_client.b") as mock_b:
            mock_b.SummarizeCommunities = AsyncMock(
                return_value=[
                    MagicMock(
                        title="T1",
                        summary="S1",
                        rating=8,
                        rating_explanation="e",
                        findings=[],
                    )
                ]
            )
            await generate_community_reports([c1, c2], entities_by_id, batch_size=2)
            assert c1.title == "T1"
            assert c2.title  # heuristic fallback, not empty
            assert c2.summary
