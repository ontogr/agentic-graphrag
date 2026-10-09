"""Tests for the entity resolution stage of one ingestion batch."""

from unittest import mock
from unittest.mock import AsyncMock
from uuid import uuid4

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.graph_schema import GENERIC
from agrag.ingestion import _resolve_stage
from agrag.ingestion._resolve_stage import resolve_stage
from agrag.ingestion.resolve.resolution import BatchResolution
from agrag.ingestion.resolve.resolver import ResolutionGroup, ResolutionResult
from agrag.loaders.types import ErrorPolicy
from agrag.retrieval.settings import RetrievalSettings


def _mention(text: str) -> ExtractedEntity:
    return ExtractedEntity(
        chunk_id=uuid4(), label="Organization", text=text, char_start=0, char_end=4
    )


class TestResolveStage:
    """Counting what the resolver decided for one batch."""

    async def test_counts_only_groups_holding_a_real_mention(self) -> None:
        """A group of only synthetic candidates is not an in-batch group."""
        entities = [_mention("Alice"), _mention("Acme")]
        result = ResolutionResult(
            groups=[
                ResolutionGroup(entity_indices=[0]),
                ResolutionGroup(entity_indices=[2]),
                ResolutionGroup(entity_indices=[1, 2]),
            ],
            matches=[],
            ambiguous_count=2,
        )
        batch = BatchResolution(
            exact_matches={
                0: Entity(id=uuid4(), label="Organization", name="Alice"),
            },
            groups=[],
            result=result,
        )

        with mock.patch.object(
            _resolve_stage, "resolve_batch", AsyncMock(return_value=batch)
        ):
            stage = await resolve_stage(
                entities,
                [],
                [],
                graph_store=AsyncMock(),
                embedder=AsyncMock(),
                vector_store=None,
                graph_schema=GENERIC,
                retrieval_settings=RetrievalSettings(),
                error_policy=ErrorPolicy.RAISE,
                job_id=None,
                tracer=None,
                max_llm_pairs=10,
            )

        assert stage.stats.in_batch_groups == 2
        assert stage.stats.exact_match_hits == 1
        assert stage.stats.ambiguous_count == 2
