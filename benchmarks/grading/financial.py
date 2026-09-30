"""Grading for FinanceBench: judged answer and evidence quality.

FinanceBench gives a reference answer and the evidence text and page of each
question. The PDFs reach the graph as Docling Markdown, so a retrieved chunk has no
page or character span and no span metric is possible. The judge compares the
answer with the reference answer, and the retrieved text with the answer and the
evidence text. The evidence pages stay in the fixture for readers.
"""

from agrag.eval import ChatModelJudge
from benchmarks.grading.base import Grade, Grader, answer_quality
from benchmarks.models import BenchmarkQuestion
from benchmarks.systems.base import SystemAnswer


class FinancialGrader(Grader):
    """Scores one answer with agrag's judged metrics, one judge sample each.

    ``correctness``, ``faithfulness`` and ``citation_accuracy`` use the reference
    answer. ``context_precision`` and ``context_recall`` use the reference answer
    followed by the evidence texts.
    """

    metrics = (
        "correctness",
        "faithfulness",
        "citation_accuracy",
        "context_precision",
        "context_recall",
    )
    # GEval correctness, about four calls for faithfulness, about five for citation
    # accuracy (one per answer sentence), two for context precision and two for
    # context recall.
    judge_calls_per_question = 14

    async def grade(
        self, question: BenchmarkQuestion, answer: SystemAnswer, judge: ChatModelJudge
    ) -> Grade:
        """Score one answer."""
        reference = question.reference
        evidence = "\n".join(item["text"] for item in reference["evidence"])
        quality = await answer_quality(
            judge,
            question,
            answer,
            reference["answer"],
            names=("correctness", "faithfulness", "citation_accuracy"),
        )
        context = await answer_quality(
            judge,
            question,
            answer,
            f"{reference['answer']}\n{evidence}",
            names=("context_precision", "context_recall"),
        )
        return Grade(scores={**quality, **context})
