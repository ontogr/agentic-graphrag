"""Tests for StageFailure's per-call truncation cap."""

import logging

import pytest

from agrag.ingestion.stats import StageFailure
from agrag.ingestion.stats.stage_failure import _MAX_FAILURES_PER_STAGE, _capped


class TestCapped:
    """_capped truncates and logs when a stage exceeds the per-call cap."""

    def test_below_cap_is_unchanged_and_silent(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Fewer failures than the cap pass through with no warning."""
        failures = [
            StageFailure(item_id=str(i), error_type="E", error_message="m")
            for i in range(3)
        ]
        with caplog.at_level(logging.WARNING):
            result = _capped(failures)
        assert result == failures
        assert caplog.records == []

    def test_above_cap_truncates_and_logs_true_count(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """More failures than the cap are truncated and the drop is logged."""
        total = _MAX_FAILURES_PER_STAGE + 5
        failures = [
            StageFailure(item_id=str(i), error_type="E", error_message="m")
            for i in range(total)
        ]
        with caplog.at_level(logging.WARNING):
            result = _capped(failures)
        assert len(result) == _MAX_FAILURES_PER_STAGE
        assert any(str(total) in record.message for record in caplog.records)
