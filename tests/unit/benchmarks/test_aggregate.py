"""Tests score aggregation: mean and count per metric, overall and per group."""

from benchmarks.grading.base import aggregate
from benchmarks.harness.record import QuestionRecord


def _question(group: str, **scores: float) -> QuestionRecord:
    return QuestionRecord(
        id=f"{group}{scores}", corpus_id="c", group=group, status="ok", scores=scores
    )


class TestAggregate:
    """Mean and count per metric, overall and per group."""

    def test_means_each_metric_overall_and_by_group(self):
        """Means each metric overall and by group."""
        scores = aggregate(
            [
                _question("a", correctness=1.0, faithfulness=0.5),
                _question("a", correctness=0.0, faithfulness=0.5),
                _question("b", correctness=1.0, faithfulness=1.0),
            ]
        )

        assert scores.aggregate["correctness"].mean == 2 / 3
        assert scores.aggregate["correctness"].n == 3
        assert scores.by_group["a"]["correctness"].mean == 0.5
        assert scores.by_group["b"]["faithfulness"].n == 1

    def test_no_questions_give_no_scores(self):
        """No questions give no scores."""
        assert aggregate([]).aggregate == {}
