"""Tests for embed_communities batching."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from agrag.common.data_models.community import Community
from agrag.ingestion.community import embed_communities


class TestEmbedCommunities:
    """embed_communities batches correctly."""

    @pytest.mark.parametrize(
        ("argument", "value"),
        [("batch_size", 0), ("max_concurrency", 0)],
    )
    async def test_rejects_invalid_batch_arguments_without_communities(
        self, argument: str, value: int
    ) -> None:
        """Reject invalid scheduling values before embedding communities."""
        embedder = AsyncMock()

        with pytest.raises(ValueError, match="must be positive"):
            await embed_communities([], embedder=embedder, **{argument: value})

        embedder.embed.assert_not_called()

    async def test_empty_communities_returns_empty_no_embed_calls(self) -> None:
        """An empty community list short-circuits without calling embed()."""
        mock_embedder = AsyncMock()
        failures = await embed_communities([], embedder=mock_embedder)
        assert failures == []
        mock_embedder.embed.assert_not_called()

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
        failures = await embed_communities(comms, embedder=mock_embedder, batch_size=2)
        assert mock_embedder.embed.call_count == 3
        assert all(c.embedding == [0.1, 0.2] for c in comms)
        assert failures == []

    async def test_batch_failure_leaves_embedding_none_and_is_recorded(self) -> None:
        """A failing batch's embed() call does not block other batches."""
        comms = [
            Community(
                id=uuid4(),
                title=f"T{i}",
                summary=f"S{i}",
                rating=5,
                rating_explanation="e",
            )
            for i in range(4)
        ]

        async def embed(texts: list[str]) -> list[list[float]]:
            if len(texts) and texts[0] == comms[0].embedding_text:
                raise RuntimeError("embedder down")
            return [[0.1, 0.2] for _ in texts]

        mock_embedder = AsyncMock()
        mock_embedder.embed = AsyncMock(side_effect=embed)
        failures = await embed_communities(comms, embedder=mock_embedder, batch_size=2)

        assert {f.item_id for f in failures} == {str(comms[0].id), str(comms[1].id)}
        assert all(f.error_type == "RuntimeError" for f in failures)
        assert comms[0].embedding is None
        assert comms[1].embedding is None
        assert comms[2].embedding == [0.1, 0.2]
        assert comms[3].embedding == [0.1, 0.2]
