"""Tests for the community_context enrichment helper."""

from unittest.mock import AsyncMock
from uuid import uuid4

from agrag.common.data_models.community import Community
from agrag.retrieval.community_context import community_context


class TestCommunityContext:
    """community_context ranks by overlap and caps at top_k."""

    async def test_empty_short_circuit(self) -> None:
        """Empty entity_ids short-circuits with no store call."""
        mock_store = AsyncMock()
        res = await community_context([], graph_store=mock_store)
        assert res == []
        mock_store.execute_read.assert_not_called()

    async def test_top_k_capping(self) -> None:
        """top_k limits returned communities."""
        mock_store = AsyncMock()
        c1, c2 = uuid4(), uuid4()
        rows = [
            {
                "c": {
                    "id": str(c1),
                    "title": "T1",
                    "summary": "S1",
                    "rating": 5,
                    "rating_explanation": "e",
                },
                "overlap": 5,
            },
            {
                "c": {
                    "id": str(c2),
                    "title": "T2",
                    "summary": "S2",
                    "rating": 5,
                    "rating_explanation": "e",
                },
                "overlap": 3,
            },
            {
                "c": {
                    "id": str(uuid4()),
                    "title": "T3",
                    "summary": "S3",
                    "rating": 5,
                    "rating_explanation": "e",
                },
                "overlap": 1,
            },
        ]
        mock_store.execute_read.return_value = rows
        res = await community_context([uuid4()], graph_store=mock_store, top_k=2)
        assert len(res) == 2
        assert res[0].score == 5

    async def test_overlap_ranking_and_parse(self) -> None:
        """Highest overlap first and parsable nodes."""
        mock_store = AsyncMock()
        cid = uuid4()
        mock_store.execute_read.return_value = [
            {
                "c": {
                    "id": str(cid),
                    "title": "T",
                    "summary": "S",
                    "rating": 5,
                    "rating_explanation": "e",
                },
                "overlap": 2,
            }
        ]
        res = await community_context([uuid4()], graph_store=mock_store, top_k=3)
        assert len(res) == 1
        assert isinstance(res[0].item, Community)
