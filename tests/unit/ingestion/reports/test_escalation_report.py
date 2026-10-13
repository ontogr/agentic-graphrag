"""Tests for EscalationReport."""

import pytest

from agrag.ingestion.reports.escalation_report import EscalationReport


def _report(
    *,
    total: int,
    eligible: int,
    escalated: int,
    lowest: float | None = None,
) -> EscalationReport:
    """Build a report whose derived fields follow its counts."""
    return EscalationReport(
        total=total,
        eligible=eligible,
        escalated=escalated,
        left_for_gliner=eligible - escalated,
        lowest_score_left=lowest,
        budget_needed=eligible / total if total else 0.0,
    )


class TestEscalationReport:
    """EscalationReport counts one run and merges across batches."""

    def test_merge_of_nothing_is_the_empty_report(self) -> None:
        """Merging no batches gives the default report."""
        assert EscalationReport.merge([]) == EscalationReport()

    def test_merge_keeps_the_run_mode_and_sums_skipped_short(self) -> None:
        """The merged report has the batches' mode and the summed short count."""
        first = EscalationReport(mode="llm", total=100, skipped_short=30, eligible=70)
        second = EscalationReport(mode="llm", total=50, skipped_short=5, eligible=45)

        merged = EscalationReport.merge([first, second])

        assert merged.mode == "llm"
        assert merged.skipped_short == 35

    def test_merge_sums_counts(self) -> None:
        """Counts add up across batches."""
        merged = EscalationReport.merge(
            [
                _report(total=100, eligible=40, escalated=20, lowest=0.6),
                _report(total=50, eligible=10, escalated=10),
            ]
        )

        assert (merged.total, merged.eligible, merged.escalated) == (150, 50, 30)
        assert merged.left_for_gliner == 20

    def test_merge_keeps_the_lowest_score_left(self) -> None:
        """The lowest score left is the minimum over batches that have one."""
        merged = EscalationReport.merge(
            [
                _report(total=10, eligible=5, escalated=1, lowest=0.7),
                _report(total=10, eligible=5, escalated=5),
                _report(total=10, eligible=5, escalated=1, lowest=0.55),
            ]
        )

        assert merged.lowest_score_left == 0.55

    def test_budget_needed_is_the_largest_batch_need(self) -> None:
        """The budget applies per batch, so the busiest batch sets the need."""
        merged = EscalationReport.merge(
            [
                _report(total=100, eligible=90, escalated=20),
                _report(total=100, eligible=10, escalated=10),
            ]
        )

        assert merged.budget_needed == pytest.approx(0.9)

    def test_merge_sums_failures_and_seconds(self) -> None:
        """Failed chunks and wall time add up across batches."""
        merged = EscalationReport.merge(
            [
                EscalationReport(
                    total=10, failed=1, primary_seconds=1.5, escalation_seconds=4.0
                ),
                EscalationReport(
                    total=10, failed=2, primary_seconds=0.5, escalation_seconds=1.0
                ),
            ]
        )

        assert merged.failed == 3
        assert merged.primary_seconds == pytest.approx(2.0)
        assert merged.escalation_seconds == pytest.approx(5.0)

    def test_merge_is_order_independent(self) -> None:
        """Batch order does not change the merged report."""
        first = _report(total=100, eligible=30, escalated=20, lowest=0.6)
        second = _report(total=40, eligible=30, escalated=8, lowest=0.5)

        assert EscalationReport.merge([first, second]) == EscalationReport.merge(
            [second, first]
        )
