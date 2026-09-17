"""Tests for generate_community_reports batching and fallbacks."""

import importlib.util
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from agrag.common.data_models.community import Community
from agrag.common.data_models.entity import Entity
from agrag.ingestion.community import generate_community_reports
from agrag.loaders.corpus.types import ErrorPolicy


baml_missing = importlib.util.find_spec("baml_py") is None


class TestGenerateCommunityReports:
    """Test community report generation and fallback behavior."""

    @pytest.mark.parametrize(
        ("argument", "value"),
        [("batch_size", 0), ("max_concurrency", 0)],
    )
    async def test_rejects_invalid_batch_arguments_without_communities(
        self, argument: str, value: int
    ) -> None:
        """Reject invalid scheduling values before processing any communities."""
        with pytest.raises(ValueError, match="must be positive"):
            await generate_community_reports([], {}, **{argument: value})

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
        failures = await generate_community_reports(
            [comm], entities_by_id, min_importance_for_llm_report=5.0
        )
        assert failures == []
        assert comm.title  # heuristic filled

    @pytest.mark.skipif(baml_missing, reason="baml extra not installed")
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
            assert c2.title == "T2"
            mock_b.SummarizeCommunities.assert_awaited_once()
            # Verify truncation: capture inputs
            captured = {}

            async def capture(communities, **kwargs):
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

    @pytest.mark.skipif(baml_missing, reason="baml extra not installed")
    async def test_out_of_range_rating_is_clamped(self) -> None:
        """An LLM rating outside 0-10 is clamped, not persisted as-is."""
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
            mock_b.SummarizeCommunities = AsyncMock(
                return_value=[
                    MagicMock(
                        title="T1",
                        summary="S1",
                        rating=42.0,
                        rating_explanation="e",
                        findings=[],
                    )
                ]
            )
            await generate_community_reports([c1], entities_by_id)
            assert c1.rating == 10.0

    @pytest.mark.skipif(baml_missing, reason="baml extra not installed")
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

    @pytest.mark.skipif(baml_missing, reason="baml extra not installed")
    async def test_batch_failure_raises_when_policy_is_raise(self) -> None:
        """RAISE policy propagates a batch failure instead of falling back."""
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
            mock_b.SummarizeCommunities = AsyncMock(side_effect=RuntimeError("down"))
            with pytest.raises(RuntimeError, match="down"):
                await generate_community_reports(
                    [c1], entities_by_id, error_policy=ErrorPolicy.RAISE
                )
            assert not c1.title

    @pytest.mark.skipif(baml_missing, reason="baml extra not installed")
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
            assert c2.title == "N2, N3"
            assert c2.rating == 5.0
