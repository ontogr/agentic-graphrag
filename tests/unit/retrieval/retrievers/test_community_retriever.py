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
