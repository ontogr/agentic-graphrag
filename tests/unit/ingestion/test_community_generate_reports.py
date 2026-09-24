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
    """Batched LLM reports with heuristic fallback."""

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
