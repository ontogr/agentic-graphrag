"""Tests for the stage-failure cap and its total/truncated signal."""

import logging

import pytest

from agrag.ingestion.stats import StageFailure
from agrag.ingestion.stats.stage_failure import (
    MAX_FAILURES_PER_STAGE,
    cap_failures,
)


class TestCapFailures:
    """cap_failures truncates and surfaces the true failure count."""

    def test_below_cap_is_unchanged_and_silent(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Fewer failures than the cap pass through with no warning."""
        failures = [
            StageFailure(item_id=str(i), error_type="E", error_message="m")
            for i in range(3)
        ]
        with caplog.at_level(logging.WARNING):
            result = cap_failures(failures)
        assert result.items == failures
        assert result.total == 3
        assert result.truncated is False
        assert caplog.records == []

    def test_above_cap_truncates_and_logs_true_count(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """More failures than the cap are truncated and the drop is logged."""
        total = MAX_FAILURES_PER_STAGE + 5
        failures = [
            StageFailure(item_id=str(i), error_type="E", error_message="m")
            for i in range(total)
        ]
        with caplog.at_level(logging.WARNING):
            result = cap_failures(failures)
        assert len(result.items) == MAX_FAILURES_PER_STAGE
        assert result.total == total
        assert result.truncated is True
        assert any(str(total) in record.message for record in caplog.records)
