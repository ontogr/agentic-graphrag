"""Tests for fail-safe LLM batch-verdict validation."""

import pytest

from agrag.ingestion.resolve import ComparisonVerdict
from agrag.ingestion.resolve.batch_validation import validate_batch_verdicts


class TestValidateBatchVerdicts:
    """Batch validation keeps every verdict bound to its requested pair."""

    @pytest.mark.parametrize(
        "results",
        [
            [],
            [{"pair_id": "unknown", "verdict": "match"}],
            [{"pair_id": "first", "verdict": "invalid"}],
            [
                {"pair_id": "first", "verdict": "match"},
                {"pair_id": "first", "verdict": "match"},
            ],
        ],
    )
    def test_rejects_missing_unknown_malformed_and_duplicate_results(
        self, results: list[object]
    ) -> None:
        """Unsafe output never confirms an entity match."""
        verdicts = validate_batch_verdicts(["first", "second"], results)

        assert verdicts["first"].verdict is ComparisonVerdict.NO_MATCH
        assert verdicts["second"].verdict is ComparisonVerdict.NO_MATCH

    def test_retains_reasoning_for_a_valid_requested_pair(self) -> None:
        """A well-formed response retains its own explanation only."""
        verdicts = validate_batch_verdicts(
            ["first", "second"],
            [{"pair_id": "second", "verdict": "match", "reasoning": "same person"}],
        )

        assert verdicts["first"].verdict is ComparisonVerdict.NO_MATCH
        assert verdicts["second"].verdict is ComparisonVerdict.MATCH
        assert verdicts["second"].reasoning == "same person"
