"""Tests for the entity resolution stage of one ingestion batch."""

from collections.abc import Callable
from unittest import mock
from unittest.mock import AsyncMock
from uuid import uuid4

from agrag.common.data_models.default_schema import DEFAULT_SCHEMA
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.ingestion import _resolve_stage
from agrag.ingestion._resolve_stage import resolve_stage
from agrag.ingestion._stage_context import StageContext
from agrag.ingestion.reports import AddResult
from agrag.ingestion.resolve.resolution import BatchResolution
from agrag.ingestion.resolve.resolver import ResolutionGroup, ResolutionResult
from agrag.loaders.types import ErrorPolicy
from agrag.observability import get_tracer


def _mention(text: str) -> ExtractedEntity:
    return ExtractedEntity(
        chunk_id=uuid4(), label="Organization", text=text, char_start=0, char_end=4
    )


class TestResolveStage:
    """Counting what the resolver decided for one batch."""

    async def test_forwards_monotonic_resolution_progress(self) -> None:
        """Resolution progress reports monotonic counts and completes at total."""
        progress: list[AddResult] = []
        batch = BatchResolution(exact_matches={}, groups=[], result=None)

        async def _resolve(
            *_args: object,
            on_progress: Callable[[int, int, float], None],
            **_kwargs: object,
        ) -> BatchResolution:
            on_progress(1, 3, 0.1)
            on_progress(2, 3, 0.2)
            on_progress(3, 3, 0.3)
            return batch

        with mock.patch.object(
            _resolve_stage, "resolve_batch", AsyncMock(side_effect=_resolve)
        ):
            ctx = StageContext(
                graph_store=AsyncMock(),
                embedder=AsyncMock(),
                error_policy=ErrorPolicy.RAISE,
                tracer=get_tracer(None),
                job_id=None,
                deferred=None,
            )
            stage = await resolve_stage(
                [_mention("Alice")],
                [],
                [],
                ctx,
                graph_schema=DEFAULT_SCHEMA,
                max_llm_pairs=10,
                on_progress=progress.append,
            )

        assert [
            (
                item.resolution.batches_done,
                item.resolution.batches_total,
                item.resolution.elapsed_seconds,
            )
            for item in progress
        ] == [(1, 3, 0.1), (2, 3, 0.2), (3, 3, 0.3)]
        assert (
            stage.stats.batches_done,
            stage.stats.batches_total,
            stage.stats.elapsed_seconds,
        ) == (3, 3, 0.3)

    async def test_counts_groups_with_two_incoming_mentions_and_copies_failures(
        self,
    ) -> None:
        """Only groups with two incoming mentions count as in-batch groups."""
        entities = [_mention(name) for name in ("Alice", "Acme", "Bob", "Eve")]
        result = ResolutionResult(
            groups=[
                ResolutionGroup(entity_indices=[0, 1]),
                ResolutionGroup(entity_indices=[2, 4]),
                ResolutionGroup(entity_indices=[5, 6]),
                ResolutionGroup(entity_indices=[3]),
            ],
            matches=[],
            ambiguous_count=2,
            failed_llm_requests=3,
            cap_truncated_pairs=4,
            llm_unavailable_pairs=5,
        )
        batch = BatchResolution(
            exact_matches={},
            groups=[],
            result=result,
        )

        with mock.patch.object(
            _resolve_stage, "resolve_batch", AsyncMock(return_value=batch)
        ):
            ctx = StageContext(
                graph_store=AsyncMock(),
                embedder=AsyncMock(),
                error_policy=ErrorPolicy.RAISE,
                tracer=get_tracer(None),
                job_id=None,
                deferred=None,
            )
            stage = await resolve_stage(
                entities,
                [],
                [],
                ctx,
                graph_schema=DEFAULT_SCHEMA,
                max_llm_pairs=10,
            )

        assert stage.stats.in_batch_groups == 1
        assert stage.stats.exact_match_hits == 0
        assert stage.stats.ambiguous_count == 2
        assert stage.stats.failed_llm_requests == 3
        assert stage.stats.cap_truncated_pairs == 4
        assert stage.stats.llm_unavailable_pairs == 5
