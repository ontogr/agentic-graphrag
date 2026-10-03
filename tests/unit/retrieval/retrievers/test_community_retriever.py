"""Tests for CommunityRetriever."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from agrag.common.data_models.vector_record import VectorHit
from agrag.retrieval.retrievers.community import CommunityRetriever
from agrag.retrieval.settings import RetrievalSettings


class TestCommunityRetriever:
    """CommunityRetriever uses community collection/top_k, not chunk's."""

    async def test_loading_query_failure_raises(self) -> None:
        """A loading query failure raises, so it is not read as no results."""
        mock_store = AsyncMock()
        mock_embedder = AsyncMock()
        mock_embedder.embed.return_value = [[0.1]]
        mock_store.execute_read.side_effect = RuntimeError("db down")

        with patch(
            "agrag.retrieval.retrievers.community.vector_search", new_callable=AsyncMock
        ) as mock_vs:
            mock_vs.return_value = [VectorHit(id=uuid4(), score=0.9, payload={})]
            retr = CommunityRetriever(graph_store=mock_store, embedder=mock_embedder)
            with pytest.raises(RuntimeError, match="db down"):
                await retr.retrieve("q")

    async def test_returns_empty_when_search_finds_nothing(self) -> None:
        """A search with no hits returns an empty list without a graph read."""
        mock_store = AsyncMock()
        mock_embedder = AsyncMock()

        with patch(
            "agrag.retrieval.retrievers.community.vector_search", new_callable=AsyncMock
        ) as mock_vs:
            mock_vs.return_value = []
            retr = CommunityRetriever(graph_store=mock_store, embedder=mock_embedder)
            res = await retr.retrieve("q")

        assert res == []
        mock_store.execute_read.assert_not_awaited()

    async def test_unparsable_row_is_skipped(self) -> None:
        """A row that fails to parse is skipped; other rows still load.

        The bad row carries the bad hit's id, so the hit is dropped by its
        row's parse failure rather than a by-id lookup miss.
        """
        mock_store = AsyncMock()
        mock_embedder = AsyncMock()
        mock_embedder.embed.return_value = [[0.1]]
        good_id = uuid4()
        bad_id = uuid4()
        mock_store.execute_read.return_value = [
            # A real UUID id matched to its hit, but a member_ids entry that
            # cannot parse into a UUID, so _parse_community_node returns None.
            {
                "n": {
                    "id": str(bad_id),
                    "title": "Bad",
                    "summary": "",
                    "rating": 0,
                    "rating_explanation": "e",
                    "member_ids": ["not-a-uuid"],
                }
            },
            {
                "n": {
                    "id": str(good_id),
                    "title": "Good",
                    "summary": "S",
                    "rating": 5,
                    "rating_explanation": "e",
                }
            },
        ]

        with patch(
            "agrag.retrieval.retrievers.community.vector_search", new_callable=AsyncMock
        ) as mock_vs:
            mock_vs.return_value = [
                VectorHit(id=bad_id, score=0.5, payload={}),
                VectorHit(id=good_id, score=0.9, payload={}),
            ]
            retr = CommunityRetriever(graph_store=mock_store, embedder=mock_embedder)
            res = await retr.retrieve("q")
            assert len(res) == 1
            assert res[0].item.title == "Good"

    async def test_zero_limit_returns_empty_without_searching(self) -> None:
        """limit=0 returns no results and never reaches vector_search."""
        mock_store = AsyncMock()
        mock_embedder = AsyncMock()
        mock_embedder.embed.return_value = [[0.1]]
        settings = RetrievalSettings(community_top_k=4)
        with patch(
            "agrag.retrieval.retrievers.community.vector_search", new_callable=AsyncMock
        ) as mock_vs:
            retr = CommunityRetriever(
                graph_store=mock_store, embedder=mock_embedder, settings=settings
            )
            res = await retr.retrieve("q", limit=0)
            assert res == []
            mock_vs.assert_not_called()
            mock_store.execute_read.assert_not_called()
