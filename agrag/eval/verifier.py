"""Verifier calibration: does the verifier give the right verdict?

Each item is a fixed ``(question, sub-questions, findings)`` input with a gold
verdict. The verdict and the gold label are both one of three values, so scoring
is an equality check and needs no judge. ``verdict_report`` gives per-class
precision, recall and F1, the macro F1 that gates, and a confusion matrix.
"""

import asyncio
from collections.abc import Sequence
from typing import Any, Literal

from deepeval.test_case import LLMTestCase
from pydantic import BaseModel
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from agrag.agents.verification import verify_findings
from agrag.eval.adapter import ScoreMetric, ScoreResult


_CONCURRENCY = 8
_LABELS = ["PASS", "INSUFFICIENT", "CONTRADICTORY"]
_ERROR = "ERROR"


class VerdictItem(BaseModel):
    """One fixed verifier input with its gold verdict.

    Attributes:
        id: A stable id for the item.
        question: The original question.
        sub_questions: The sub-questions the question was split into.
        findings: The findings text with citation keys such as ``E1``.
        gold: The verdict the verifier should give.
        human_reviewed: True when a person confirmed the gold label.
    """

    id: str
    question: str
    sub_questions: list[str]
    findings: str
    gold: Literal["PASS", "INSUFFICIENT", "CONTRADICTORY"]
    human_reviewed: bool = False


class ClassScores(BaseModel):
    """Precision, recall and F1 of one verdict class."""

    precision: float
    recall: float
    f1: float


class VerdictReport(BaseModel):
    """Scores of predicted verdicts against gold verdicts.

    Attributes:
        labels: The class order of ``confusion_matrix``.
        per_class: Scores for each class.
        macro_f1: The mean F1 over the three classes.
        confusion_matrix: Counts with gold classes as rows and predicted classes
            as columns. A prediction of ``ERROR`` is in no column.
        errors: The number of ``ERROR`` predictions. Each one is a miss for
            the gold class of its item.
    """

    labels: list[str]
    per_class: dict[str, ClassScores]
    macro_f1: float
    confusion_matrix: list[list[int]]
    errors: int


async def run_verifier(
    model: Any,
    items: Sequence[VerdictItem],
    *,
    concurrency: int = _CONCURRENCY,
) -> list[str]:
    """Run the verifier over items and return one label per item.

    A call that raises gives the label ``ERROR``. It is wrong for every gold
    class and shows in the report. It is never dropped.

    Args:
        model: The chat model under test.
        items: The fixed inputs.
        concurrency: The most calls that run at once. Lower it for an endpoint
            that limits concurrent requests.

    Returns:
        One verdict label per item, in the order of ``items``.

    Raises:
        ValueError: ``concurrency`` is less than 1.
    """
    if concurrency < 1:
        raise ValueError(f"concurrency must be at least 1, got {concurrency}")
    semaphore = asyncio.Semaphore(concurrency)

    async def run(item: VerdictItem) -> str:
        async with semaphore:
            try:
                result = await verify_findings(
                    model, item.question, item.sub_questions, item.findings
                )
            except Exception:
                return _ERROR
        return result.status

    return list(await asyncio.gather(*(run(item) for item in items)))


def verdict_case(item: VerdictItem, predicted: str) -> LLMTestCase:
    """Build a test case with the predicted and the gold verdict.

    Args:
        item: The fixed input.
        predicted: The label from ``run_verifier``.
    """
    return LLMTestCase(
        input=item.question, actual_output=predicted, expected_output=item.gold
    )


def verdict_match_metric(*, threshold: float = 0.0) -> ScoreMetric:
    """Build a metric that scores 1.0 when the verdict equals the gold verdict.

    The default threshold is 0 because the gate belongs on the macro F1 of
    ``verdict_report``.

    Args:
        threshold: The minimum case score that counts as success.
    """

    def scorer(test_case: LLMTestCase) -> ScoreResult:
        match = test_case.actual_output == test_case.expected_output
        return ScoreResult(
            float(match),
            f"predicted {test_case.actual_output}, gold {test_case.expected_output}",
            {},
        )

    return ScoreMetric("Verdict match", scorer, threshold)


def verdict_report(gold: Sequence[str], predicted: Sequence[str]) -> VerdictReport:
    """Score predicted verdicts against gold verdicts.

    Args:
        gold: The gold label of each item.
        predicted: The label of each item from ``run_verifier``.

    Returns:
        Per-class scores, macro F1, the confusion matrix and the error count.
    """
    precision, recall, f1, _ = precision_recall_fscore_support(
        gold, predicted, labels=_LABELS, zero_division=0
    )
    matrix = confusion_matrix(gold, predicted, labels=_LABELS)
    return VerdictReport(
        labels=_LABELS,
        per_class={
            label: ClassScores(precision=float(p), recall=float(r), f1=float(f))
            for label, p, r, f in zip(_LABELS, precision, recall, f1, strict=True)
        },
        macro_f1=float(f1.mean()),
        confusion_matrix=matrix.tolist(),
        errors=sum(label == _ERROR for label in predicted),
    )
