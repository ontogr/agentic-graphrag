"""Tests for CommunityRetriever."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agrag.common.data_models.vector_record import VectorHit
from agrag.retrieval.retrievers.community import CommunityRetriever
from agrag.retrieval.settings import RetrievalSettings


class TestCommunityRetriever:
    """CommunityRetriever uses community collection/top_k, not chunk's."""

    async def test_uses_community_collection_and_top_k(self) -> None:
        """Retriever forwards community_collection and community_top_k."""
        mock_store = AsyncMock()
        mock_embedder = AsyncMock()
        mock_embedder.embed.return_value = [[0.1, 0.2]]
        settings = RetrievalSettings(community_collection="my_comm", community_top_k=4)

        fake_hits = [VectorHit(id=uuid4(), score=0.9, payload={})]
        with patch(
            "agrag.retrieval.retrievers.community.vector_search", new_callable=AsyncMock
        ) as mock_vs:
            mock_vs.return_value = fake_hits
            cid = fake_hits[0].id
            mock_store.execute_read.return_value = [
                {
                    "n": {
                        "id": str(cid),
                        "title": "T",
                        "summary": "S",
                        "rating": 5,
                        "rating_explanation": "e",
                    }
                }
            ]
            retr = CommunityRetriever(
                graph_store=mock_store, embedder=mock_embedder, settings=settings
            )
            res = await retr.retrieve("q")
            assert mock_vs.call_args[1]["collection"] == "my_comm"
            assert mock_vs.call_args[1]["labels"] == ["Community"]
            assert mock_vs.call_args[1]["limit"] == 4
            assert len(res) == 1

    async def test_not_chunk_collection(self) -> None:
        """Community retriever does not use chunk_collection."""
        mock_store = AsyncMock()
        mock_embedder = AsyncMock()
        mock_embedder.embed.return_value = [[0.1]]
        settings = RetrievalSettings(
            chunk_collection="agrag_chunks", community_collection="agrag_communities"
        )
        with patch(
            "agrag.retrieval.retrievers.community.vector_search", new_callable=AsyncMock
        ) as mock_vs:
            mock_vs.return_value = []
            retr = CommunityRetriever(
                graph_store=mock_store, embedder=mock_embedder, settings=settings
            )
            await retr.retrieve("q")
            assert mock_vs.call_args[1]["collection"] == "agrag_communities"

    async def test_hydration_query_raises_returns_empty(self) -> None:
        """A hydration query failure returns no results, not an exception."""
        mock_store = AsyncMock()
        mock_embedder = AsyncMock()
        mock_embedder.embed.return_value = [[0.1]]
        mock_store.execute_read.side_effect = RuntimeError("db down")

        with patch(
            "agrag.retrieval.retrievers.community.vector_search", new_callable=AsyncMock
        ) as mock_vs:
            mock_vs.return_value = [VectorHit(id=uuid4(), score=0.9, payload={})]
            retr = CommunityRetriever(graph_store=mock_store, embedder=mock_embedder)
            res = await retr.retrieve("q")
            assert res == []

    async def test_unparsable_row_is_skipped(self) -> None:
        """A row that fails to parse is skipped; other rows still hydrate."""
        mock_store = AsyncMock()
        mock_embedder = AsyncMock()
        mock_embedder.embed.return_value = [[0.1]]
        good_id = uuid4()
        bad_id = uuid4()
        mock_store.execute_read.return_value = [
            {"n": {"id": "not-a-uuid", "title": "Bad", "summary": "", "rating": 0}},
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

    async def test_explicit_zero_limit_is_preserved(self) -> None:
        """limit=0 is honored, not replaced by community_top_k."""
        mock_store = AsyncMock()
        mock_embedder = AsyncMock()
        mock_embedder.embed.return_value = [[0.1]]
        settings = RetrievalSettings(community_top_k=4)
        with patch(
            "agrag.retrieval.retrievers.community.vector_search", new_callable=AsyncMock
        ) as mock_vs:
            mock_vs.return_value = []
            retr = CommunityRetriever(
                graph_store=mock_store, embedder=mock_embedder, settings=settings
            )
            await retr.retrieve("q", limit=0)
            assert mock_vs.call_args[1]["limit"] == 0
