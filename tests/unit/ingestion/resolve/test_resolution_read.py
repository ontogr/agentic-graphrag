"""Tests for bounded telemetry reads during entity resolution."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from agrag.common.data_models.extraction import ExtractedEntity
from agrag.ingestion.resolve.resolution import (
    _already_decided_pairs,
    resolve_batch,
)
from agrag.loaders.types import ErrorPolicy


class _FakeEmbedder:
    """Return stable vectors for the resolver's fuzzy comparison."""

    async def embed_one(self, text: str) -> list[float]:
        """Return one fixed vector."""
        return [0.1, 0.2]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one fixed vector per text."""
        return [[0.1, 0.2] for _ in texts]


def _mention(text: str) -> ExtractedEntity:
    """Build a mention for resolution-read tests."""
    return ExtractedEntity(
        chunk_id=uuid4(), label="Person", text=text, char_start=0, char_end=len(text)
    )


def _node(entity_id: object, name: str) -> dict[str, object]:
    """Build the node payload a merge-key read returns."""
    return {
        "id": str(entity_id),
        "name": name,
        "merge_key": f"Person:{name.lower()}",
        "merge_count": 1,
        "source_chunk_ids": [],
        "created_at": "2020-01-01T00:00:00+00:00",
    }


class TestAlreadyDecidedPairs:
    """The telemetry read covers only resolver candidates."""

    async def test_reads_and_returns_only_candidate_pairs(self) -> None:
        """Non-candidate ids are not sent to the database read."""
        first_id, second_id, other_id = uuid4(), uuid4(), uuid4()
        store = AsyncMock()
        store.execute_read.return_value = [
            {"a_id": str(first_id), "b_id": str(second_id)},
            {"a_id": str(first_id), "b_id": str(other_id)},
        ]

        decided, failure = await _already_decided_pairs(
            {0: first_id, 1: second_id, 2: other_id},
            {0: [1], 1: [0]},
            store,
        )

        assert decided == {(0, 1)}
        assert failure is None
        params = store.execute_read.await_args.args[1]
        assert params["pairs"] == [sorted((str(first_id), str(second_id)))]

    async def test_skips_read_failure_and_returns_a_stage_failure(self) -> None:
        """A non-raising policy reports telemetry failure without raising."""
        store = AsyncMock()
        store.execute_read.side_effect = RuntimeError("database unavailable")

        decided, failure = await _already_decided_pairs(
            {0: uuid4(), 1: uuid4()},
            {0: [1]},
            store,
        )

        assert decided == set()
        assert failure is not None
        assert failure.item_id == "already_decided_pairs"
        assert failure.error_type == "RuntimeError"
        assert failure.error_message == "database unavailable"


class TestResolveBatchTelemetryRead:
    """Failure of the already-decided read does not change comparisons."""

    @pytest.mark.parametrize("error_policy", [ErrorPolicy.SKIP, ErrorPolicy.RAISE])
    async def test_reports_failure_and_keeps_candidate_comparisons(
        self, error_policy: ErrorPolicy
    ) -> None:
        """A telemetry read failure is reported without marking mentions failed."""
        first_id, second_id = uuid4(), uuid4()
        store = AsyncMock()
        store.execute_read.side_effect = [
            [
                {"n": _node(first_id, "Ada")},
                {"n": _node(second_id, "Ada Lovelace")},
            ],
            RuntimeError("telemetry read unavailable"),
        ]

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new=AsyncMock(return_value=[]),
        ):
            batch = await resolve_batch(
                [_mention("Ada"), _mention("Ada Lovelace")],
                [],
                {},
                graph_store=store,
                embedder=_FakeEmbedder(),
                entity_labels=["Person"],
                tracer=None,
                max_llm_pairs=0,
                error_policy=error_policy,
            )

        assert batch.result is not None
        assert {0, 1} in [set(group.entity_indices) for group in batch.result.groups]
        assert batch.unresolved_indices == set()
        assert len(batch.failures) == 1
        assert batch.failures[0].item_id == "already_decided_pairs"
        assert batch.failures[0].error_message == "telemetry read unavailable"
        assert store.execute_read.await_count == 2
