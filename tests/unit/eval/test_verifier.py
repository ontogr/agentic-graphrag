"""Tests for verifier calibration scoring and the batch runner.

The runner uses a scripted model, so no endpoint is called. The report tests
check the rules that are not plain sklearn arithmetic: fixed label order, error
handling and classes that never appear.
"""

from typing import Any

import pytest

from agrag.agents.verification import VerificationResult
from agrag.eval import (
    VerdictItem,
    run_verifier,
    verdict_case,
    verdict_match_metric,
    verdict_report,
)


LABELS = ["PASS", "INSUFFICIENT", "CONTRADICTORY"]


class _ScriptedModel:
    """Chat model stand-in that answers by the question text."""

    def __init__(self, verdicts: dict[str, str]) -> None:
        """Map each question to a status; ``boom`` questions raise."""
        self.verdicts = verdicts
        self.question = ""

    def with_structured_output(self, schema: Any, **kwargs: Any) -> "_ScriptedModel":
        """Return self; the reply is built in ``ainvoke``."""
        return self

    async def ainvoke(self, messages: list[Any]) -> VerificationResult:
        """Answer from the question found in the user message."""
        text = messages[-1].content
        for question, status in self.verdicts.items():
            if question in text:
                if status == "boom":
                    raise RuntimeError("endpoint down")
                return VerificationResult(reasoning="r", status=status)
        raise AssertionError(text)


def _item(name: str, gold: str) -> VerdictItem:
    """Build an item whose question is its name."""
    return VerdictItem(
        id=name,
        question=name,
        sub_questions=[name],
        findings=f"[E1] {name}",
        gold=gold,
    )


class TestRunVerifier:
    """run_verifier returns one label per item and never drops one."""

    async def test_error_item_is_labelled_and_others_are_kept(self) -> None:
        """A raising item becomes ERROR and counts as a miss in the report."""
        items = [_item("qa", "PASS"), _item("qb", "PASS"), _item("qc", "PASS")]
        model = _ScriptedModel({"qa": "PASS", "qb": "boom", "qc": "PASS"})

        predicted = await run_verifier(model, items, concurrency=2)
        report = verdict_report([i.gold for i in items], predicted)

        assert predicted == ["PASS", "ERROR", "PASS"]
        assert report.errors == 1
        assert report.per_class["PASS"].recall == pytest.approx(2 / 3)

    async def test_concurrency_below_one_is_rejected(self) -> None:
        """A zero limit would hang, so it is an error."""
        with pytest.raises(ValueError, match="concurrency"):
            await run_verifier(_ScriptedModel({}), [], concurrency=0)


class TestVerdictReport:
    """verdict_report scores three fixed classes."""

    def test_perfect_predictions_give_macro_f1_one(self) -> None:
        """Every class right gives 1.0."""
        gold = LABELS * 2

        assert verdict_report(gold, gold).macro_f1 == 1.0

    def test_always_pass_scores_well_below_one(self) -> None:
        """A verifier that always says PASS is not calibrated."""
        gold = LABELS * 4

        assert verdict_report(gold, ["PASS"] * len(gold)).macro_f1 < 0.5

    def test_class_never_predicted_scores_zero_without_error(self) -> None:
        """No prediction of a class gives 0 precision and 0 recall."""
        report = verdict_report(["PASS", "INSUFFICIENT"], ["PASS", "PASS"])

        assert report.per_class["INSUFFICIENT"].precision == 0.0
        assert report.per_class["INSUFFICIENT"].recall == 0.0

    def test_confusion_matrix_rows_follow_the_fixed_label_order(self) -> None:
        """Rows are gold, columns are predicted, in PASS/INSUFFICIENT/CONTRADICTORY."""
        report = verdict_report(
            ["PASS", "INSUFFICIENT", "CONTRADICTORY"],
            ["INSUFFICIENT", "INSUFFICIENT", "PASS"],
        )

        assert report.labels == LABELS
        assert report.confusion_matrix == [[0, 1, 0], [0, 1, 0], [1, 0, 0]]

    def test_error_counts_as_a_miss_and_is_reported(self) -> None:
        """ERROR lowers recall and shows in the error count."""
        report = verdict_report(["PASS", "PASS"], ["PASS", "ERROR"])

        assert report.errors == 1
        assert report.per_class["PASS"].recall == 0.5


class TestVerdictMatchMetric:
    """The match metric is 1.0 on equal labels."""

    @pytest.mark.parametrize(("predicted", "score"), [("PASS", 1.0), ("ERROR", 0.0)])
    def test_scores_equality(self, predicted: str, score: float) -> None:
        """Equal gold and predicted labels score 1.0, others 0.0."""
        metric = verdict_match_metric()

        assert metric.measure(verdict_case(_item("q", "PASS"), predicted)) == score
