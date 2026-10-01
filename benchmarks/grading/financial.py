"""Grading for FinanceBench: judged answer and evidence quality.

FinanceBench gives a reference answer and the evidence text and page of each
question. The PDFs reach the graph as Docling Markdown, so a retrieved chunk has no
page or character span and no span metric is possible. The judge compares the
answer with the reference answer, and the retrieved text with the answer and the
evidence text. The evidence pages stay in the fixture for readers.

Lite mode scores two metrics to keep its judge cost low. Full mode scores five.
"""

from agrag.eval import ChatModelJudge
from benchmarks.grading.base import Grade, Grader, answer_quality
from benchmarks.models import BenchmarkQuestion
from benchmarks.systems.base import SystemAnswer


_CORRECTNESS_CALLS = 1
_FAITHFULNESS_CALLS = 4
_CONTEXT_PRECISION_CALLS = 2
_CONTEXT_RECALL_CALLS = 2
# Cited sentences in an answer that the full-mode estimate allows for.
_MAX_CITED_SENTENCES = 10


class FinancialGrader(Grader):
    """Scores one answer with agrag's judged metrics, one judge sample each.

    ``correctness``, ``faithfulness`` and ``citation_accuracy`` use the reference
    answer. ``context_precision`` and ``context_recall`` use the reference answer
    followed by the evidence texts. A lite grader scores only ``correctness`` and
    ``context_recall``.
    """

    def __init__(self, *, full: bool = False) -> None:
        """Choose the metrics.

        Args:
            full: Whether to score all five metrics instead of the two of lite mode.
        """
        if full:
            self.metrics = (
                "correctness",
                "faithfulness",
                "citation_accuracy",
                "context_precision",
                "context_recall",
            )
            # Citation accuracy makes one call per cited sentence and no limit
            # exists on answer length, so the estimate assumes a long answer. An
            # answer with more cited sentences costs more than the estimate.
            self.judge_calls_per_question = (
                _CORRECTNESS_CALLS
                + _FAITHFULNESS_CALLS
                + _MAX_CITED_SENTENCES
                + _CONTEXT_PRECISION_CALLS
                + _CONTEXT_RECALL_CALLS
            )
        else:
            self.metrics = ("correctness", "context_recall")
            # One GEval call for correctness and about two for context recall.
            self.judge_calls_per_question = 3

    async def grade(
        self, question: BenchmarkQuestion, answer: SystemAnswer, judge: ChatModelJudge
    ) -> Grade:
        """Score one answer.

        Args:
            question: The question, with its reference answer and evidence.
            answer: The answer of the system.
            judge: The judge model.

        Returns:
            The score of each metric of this grader.
        """
        reference = question.reference
        evidence = "\n".join(item["text"] for item in reference["evidence"])
        answer_names = tuple(
            name
            for name in self.metrics
            if name in ("correctness", "faithfulness", "citation_accuracy")
        )
        evidence_names = tuple(
            name for name in self.metrics if name.startswith("context_")
        )
        quality = await answer_quality(
            judge, question, answer, reference["answer"], names=answer_names
        )
        context = await answer_quality(
            judge,
            question,
            answer,
            f"{reference['answer']}\n{evidence}",
            names=evidence_names,
        )
        return Grade(scores={**quality, **context})
