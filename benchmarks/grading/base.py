"""Grading: domain graders and the aggregation of their scores."""

import asyncio
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from deepeval.metrics import BaseMetric

from agrag.eval import (
    ChatModelJudge,
    CitationAccuracyMetric,
    answer_case,
    context_precision,
    context_recall,
    correctness,
    faithfulness,
)
from benchmarks.harness.record import MetricScore, QuestionRecord, Scores
from benchmarks.models import BenchmarkQuestion
from benchmarks.systems.base import SystemAnswer


_NEEDS_EVIDENCE = ("faithfulness", "context_precision", "context_recall")


@dataclass
class Grade:
    """The scores of one question.

    Attributes:
        scores: The score of each metric, from 0 to 1.
        flags: Domain facts to store on the question record.
    """

    scores: dict[str, float]
    flags: list[str] = field(default_factory=list)


class Grader(ABC):
    """Grades the answers of one domain. Every judged metric runs once.

    Attributes:
        metrics: The metric names a grade holds. An agent failure scores 0 on each.
        judge_calls_per_question: The judge calls one question needs, for the dry
            run.
    """

    metrics: tuple[str, ...]
    judge_calls_per_question: int

    @abstractmethod
    async def grade(
        self, question: BenchmarkQuestion, answer: SystemAnswer, judge: ChatModelJudge
    ) -> Grade:
        """Score one answer."""


async def answer_quality(
    judge: ChatModelJudge,
    question: BenchmarkQuestion,
    answer: SystemAnswer,
    reference: str,
    names: Sequence[str] = ("correctness",),
) -> dict[str, float]:
    """Score an agrag answer with ``agrag.eval`` metrics, one judge sample each.

    Args:
        judge: The judge.
        question: The question.
        answer: The agrag answer. Its ``raw`` field is the agent result.
        reference: The reference answer.
        names: Metrics to run: ``correctness``, ``faithfulness``,
            ``context_precision``, ``context_recall`` and ``citation_accuracy``.
            A metric that needs evidence scores 0 when the agent saw none.

    Returns:
        A score for each name.
    """
    factories: dict[str, BaseMetric] = {
        "correctness": correctness(judge),
        "faithfulness": faithfulness(judge),
        "context_precision": context_precision(judge),
        "context_recall": context_recall(judge),
        "citation_accuracy": CitationAccuracyMetric(judge),
    }
    case = answer_case(question.query, answer.raw, reference)
    scores = dict.fromkeys(names, 0.0)
    metrics = {
        name: factories[name]
        for name in names
        if case.retrieval_context or name not in _NEEDS_EVIDENCE
    }
    await asyncio.gather(*(metric.a_measure(case) for metric in metrics.values()))
    scores.update({name: metric.score or 0.0 for name, metric in metrics.items()})
    return scores


def aggregate(questions: Sequence[QuestionRecord]) -> Scores:
    """Average each metric over all questions and over each group."""

    def means(rows: Sequence[QuestionRecord]) -> dict[str, MetricScore]:
        values: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            for name, score in row.scores.items():
                values[name].append(score)
        return {
            name: MetricScore(mean=sum(v) / len(v), n=len(v))
            for name, v in values.items()
        }

    groups: dict[str, list[QuestionRecord]] = defaultdict(list)
    for question in questions:
        groups[question.group].append(question)
    return Scores(
        aggregate=means(questions),
        by_group={name: means(rows) for name, rows in sorted(groups.items())},
    )
