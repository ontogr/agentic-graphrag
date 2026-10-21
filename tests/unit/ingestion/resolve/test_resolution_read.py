"""Tests for bounded telemetry reads during entity resolution."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

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

        decided = await _already_decided_pairs(
            {0: first_id, 1: second_id, 2: other_id},
            {0: [1], 1: [0]},
            store,
            tracer=TracerProvider().get_tracer(__name__),
        )

        assert decided == {(0, 1)}
        params = store.execute_read.await_args.args[1]
        assert params["pairs"] == [sorted((str(first_id), str(second_id)))]

    async def test_skips_read_without_recording(self) -> None:
        """Disabled tracing never issues the diagnostic database read."""
        store = AsyncMock()
        store.execute_read.side_effect = RuntimeError("database unavailable")

        decided = await _already_decided_pairs(
            {0: uuid4(), 1: uuid4()},
            {0: [1]},
            store,
        )

        assert decided == set()
        store.execute_read.assert_not_awaited()


class TestResolveBatchTelemetryRead:
    """Failure of the already-decided read does not change comparisons."""

    @pytest.mark.parametrize("error_policy", [ErrorPolicy.SKIP, ErrorPolicy.RAISE])
    async def test_traces_failure_and_keeps_candidate_comparisons(
        self, error_policy: ErrorPolicy
    ) -> None:
        """Telemetry failure is traced without entering ingestion failures."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
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
                tracer=provider.get_tracer(__name__),
                max_llm_pairs=0,
                error_policy=error_policy,
            )

        assert batch.result is not None
        assert {0, 1} in [set(group.entity_indices) for group in batch.result.groups]
        assert batch.unresolved_indices == set()
        assert batch.failures == []
        assert store.execute_read.await_count == 2
        diagnostic = next(
            span
            for span in exporter.get_finished_spans()
            if span.name == "agrag.resolution.decided_pairs"
        )
        assert any(
            event.name == "exception"
            and (event.attributes or {}).get("exception.message")
            == "telemetry read unavailable"
            for event in diagnostic.events
        )
