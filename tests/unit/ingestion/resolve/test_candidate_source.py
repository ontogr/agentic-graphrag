"""Tests for GraphCandidateSource.global_candidates_for.

Covers the VectorStore-backed candidate path, which must hydrate the
persisted Entity by id rather than reconstructing its name from the display
text. Patches ``agrag.ingestion.resolve.candidate_source.vector_search`` the
way ``tests/unit/retrieval/retrievers/test_entity.py`` patches its
module-local ``vector_search`` import.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.vector_record import VectorHit
from agrag.ingestion.resolve.candidate_source import GraphCandidateSource


class MockEmbedder:
    """Mock embedder for candidate-source tests."""

    async def embed_one(self, text: str) -> list[float]:
        """Method under test."""
        return [0.1, 0.2]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Method under test."""
        return [[0.1, 0.2] for _ in texts]


def _mention(text: str, label: str = "Show") -> ExtractedEntity:
    """Build a mention for candidate-source tests."""
    return ExtractedEntity(
        chunk_id=uuid4(),
        label=label,
        text=text,
        char_start=0,
        char_end=len(text),
    )


class TestGraphCandidateSourceGlobalCandidatesFor:
    """global_candidates_for resolves vector hits into persisted entities."""

    async def test_returns_untruncated_name_for_vector_store_hit(self) -> None:
        """A colon in the real name is not truncated by the VectorStore path.

        Regression: the payload only carries embedding_text under "text", so
        guessing the name by splitting on ":" turned "Star Trek: Voyager"
        into "Star Trek". The fix hydrates the real node by id instead.
        """
        entity_id = uuid4()
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = [
            {
                "n": {
                    "id": str(entity_id),
                    "labels": ["Show", "_AgragNode"],
                    "properties": {"name": "Star Trek: Voyager"},
                }
            }
        ]
        source = GraphCandidateSource(
            graph_store=graph_store,
            embedder=MockEmbedder(),
            vector_store=AsyncMock(),
            vector_collection="entities",
        )

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[
                VectorHit(
                    id=entity_id,
                    score=0.9,
                    payload={"label": "Show", "text": "Star Trek: Voyager"},
                )
            ],
        ):
            candidates = await source.global_candidates_for(
                _mention("Star Trek: Voyager")
            )

        assert len(candidates) == 1
        assert candidates[0].name == "Star Trek: Voyager"

    async def test_skips_hits_that_fail_to_hydrate(self) -> None:
        """A hit whose node cannot be hydrated is dropped, not guessed."""
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = []
        source = GraphCandidateSource(
            graph_store=graph_store,
            embedder=MockEmbedder(),
            vector_store=AsyncMock(),
            vector_collection="entities",
        )

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[
                VectorHit(
                    id=uuid4(),
                    score=0.9,
                    payload={"label": "Show", "text": "Star Trek: Voyager"},
                )
            ],
        ):
            candidates = await source.global_candidates_for(
                _mention("Star Trek: Voyager")
            )

        assert candidates == []

    async def test_native_path_validates_payload_directly(self) -> None:
        """With no VectorStore, the native payload already has the real name.

        The native path must not be touched by the hydrate-by-id fix, and
        must not issue a graph read to get the name.
        """
        entity_id = uuid4()
        graph_store = AsyncMock()
        source = GraphCandidateSource(
            graph_store=graph_store, embedder=MockEmbedder(), vector_store=None
        )

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[
                VectorHit(
                    id=entity_id,
                    score=0.9,
                    payload={"name": "Star Trek: Voyager"},
                )
            ],
        ):
            candidates = await source.global_candidates_for(
                _mention("Star Trek: Voyager")
            )

        graph_store.execute_read.assert_not_called()
        assert len(candidates) == 1
        assert candidates[0].name == "Star Trek: Voyager"
