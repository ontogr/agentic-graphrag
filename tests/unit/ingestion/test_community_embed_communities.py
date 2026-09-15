"""Tests for embed_communities batching."""

from unittest.mock import AsyncMock
from uuid import uuid4

from agrag.common.data_models.community import Community
from agrag.ingestion.community import embed_communities


class TestEmbedCommunities:
    """embed_communities batches correctly."""

    async def test_batches(self) -> None:
        """More communities than batch_size results in multiple embed calls."""
        comms = [
            Community(
                id=uuid4(),
                title=f"T{i}",
                summary=f"S{i}",
                rating=5,
                rating_explanation="e",
            )
            for i in range(5)
        ]
        mock_embedder = AsyncMock()
        mock_embedder.embed = AsyncMock(
            side_effect=lambda texts: [[0.1, 0.2] for _ in texts]
        )
        await embed_communities(comms, embedder=mock_embedder, batch_size=2)
        assert mock_embedder.embed.call_count == 3
        assert all(c.embedding == [0.1, 0.2] for c in comms)
