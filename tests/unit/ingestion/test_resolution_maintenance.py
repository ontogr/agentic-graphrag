"""Tests for the failure counts that consolidate() reports."""

from types import SimpleNamespace
from unittest import mock
from unittest.mock import AsyncMock
from uuid import uuid4

from agrag.common.data_models.entity import Entity
from agrag.ingestion import _resolution_maintenance
from agrag.ingestion.resolve.resolver import ResolutionGroup, ResolutionResult
from agrag.observability import get_tracer


def _result(failed: int, capped: int, unavailable: int) -> ResolutionResult:
    """Build a resolver result with only singleton groups and failure counts."""
    return ResolutionResult(
        groups=[
            ResolutionGroup(entity_indices=[0]),
            ResolutionGroup(entity_indices=[1]),
        ],
        matches=[],
        failed_llm_requests=failed,
        cap_truncated_pairs=capped,
        llm_unavailable_pairs=unavailable,
    )


class TestConsolidateFailureCounts:
    """consolidate() sums resolver failure counts over every label."""

    @staticmethod
    async def test_sums_failure_counts_over_labels() -> None:
        """Two labels with failures report their summed counts."""
        schema = SimpleNamespace(
            entities=[SimpleNamespace(label="Person"), SimpleNamespace(label="Org")]
        )
        entities = [
            Entity(id=uuid4(), label="Person", name="Jon Smith"),
            Entity(id=uuid4(), label="Person", name="John Smith"),
        ]
        results = [(_result(1, 2, 3), []), (_result(10, 20, 30), [])]

        with (
            mock.patch.object(
                _resolution_maintenance,
                "all_entities_by_label",
                AsyncMock(return_value=entities),
            ),
            mock.patch.object(
                _resolution_maintenance,
                "resolve_persisted",
                AsyncMock(side_effect=results),
            ),
        ):
            report = await _resolution_maintenance.consolidate(
                apply=False,
                schema=schema,
                graph_store=AsyncMock(),
                embedder=AsyncMock(),
                tracer=get_tracer(None),
                max_llm_pairs=500,
            )

        assert report.failed_llm_requests == 11
        assert report.cap_truncated_pairs == 22
        assert report.llm_unavailable_pairs == 33
