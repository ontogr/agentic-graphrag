"""Citation gate decision for the answer-quality eval, without a judge call."""

import statistics
from typing import TypedDict

from agrag.eval.answer import CitationScoreBreakdown


# Citation accuracy mean that fails the run. Historical means span 0.243 to
# 0.583 with no product change, so only a collapse fails. Between this floor
# and the historical 0.25 level the run passes with a printed warning.
CITATION_ACCURACY_FLOOR = 0.15
CITATION_ACCURACY_WARN = 0.25


class _CitationAccuracyScore(TypedDict):
    """The ``citation_accuracy`` entry in one question's report row."""

    score: float
    breakdown: CitationScoreBreakdown


class AnswerQualityRow(TypedDict):
    """One question's report row, restricted to what the gate reads.

    The report holds more fields (question, answer, other metrics); only the
    ones the gate reads are declared here.
    """

    id: str
    scores: dict[str, _CitationAccuracyScore]


def citation_gate(
    rows: list[AnswerQualityRow],
) -> tuple[list[tuple[str, str, list[str]]], float, bool]:
    """Decide the citation gate from the report rows, without a judge call.

    Args:
        rows: One report row per question, each holding the citation accuracy
            breakdown with its sentence rows.

    Returns:
        The fabricated citations as (question id, sentence, keys), the
        citation accuracy mean, and whether the mean sits in the warn band
        between the collapse floor and the historical level.

    Raises:
        KeyError: A breakdown has no sentence rows.
        statistics.StatisticsError: There are no rows.
    """
    fabricated = [
        (row["id"], sentence["text"], sentence["keys"])
        for row in rows
        for sentence in row["scores"]["citation_accuracy"]["breakdown"]["sentence_rows"]
        if sentence["fabricated"]
    ]
    mean = statistics.mean(row["scores"]["citation_accuracy"]["score"] for row in rows)
    return fabricated, mean, CITATION_ACCURACY_FLOOR <= mean < CITATION_ACCURACY_WARN
