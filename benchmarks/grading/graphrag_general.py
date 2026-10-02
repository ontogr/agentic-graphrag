"""Grading for GraphRAG-Bench: judged quality, ROUGE-L and the official accuracy.

The evidence items of a question are paraphrases written by a language model, and
most Creative Generation evidence is invented persona content, so no span metric
is possible. ``context_recall`` asks the judge whether the retrieved text covers the
evidence items, so read it with that caveat.

ROUGE-L scores every question, but the benchmark reports it for Fact Retrieval and
Complex Reasoning only. Read it in those groups.

Lite mode scores three metrics to keep its judge cost low. Full mode scores five.
"""

from rouge_score import rouge_scorer

from agrag.embedding.base import Embedder
from agrag.embedding.sentence_transformers import SentenceTransformerEmbedder
from agrag.eval import ChatModelJudge
from benchmarks.grading.base import Grade, Grader, answer_quality
from benchmarks.grading.graphrag_accuracy import answer_accuracy
from benchmarks.models import BenchmarkQuestion
from benchmarks.systems.base import SystemAnswer


def rouge_l(answer: str, reference: str) -> float:
    """Return the ROUGE-L F-measure of an answer, as the benchmark's scorer does.

    The scorer stems words, and a blank answer or reference scores 0.
    """
    if not answer.strip() or not reference.strip():
        return 0.0
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    return scorer.score(reference, answer)["rougeL"].fmeasure


_CORRECTNESS_CALLS = 1
_FAITHFULNESS_CALLS = 4
_CONTEXT_RECALL_CALLS = 2
_ACCURACY_CALLS = 3


class GraphRagGrader(Grader):
    """Scores one answer with agrag's judged metrics and the benchmark's own.

    ``correctness`` and ``faithfulness`` use the gold answer and the retrieved text.
    ``context_recall`` uses the evidence items. ``rouge_l`` and ``official_accuracy``
    follow the benchmark's scorer. The embedder of the accuracy metric loads on the
    first answer, with the same model settings as the run's embedder. A lite grader
    scores only ``correctness``, ``rouge_l`` and ``official_accuracy``.
    """

    def __init__(self, embedder: Embedder | None = None, *, full: bool = False) -> None:
        """Build the grader.

        Args:
            embedder: The embedder of the accuracy metric, or None to load the
                default local model on the first answer.
            full: Whether to score all five metrics instead of the three of lite
                mode.
        """
        self._embedder = embedder
        if full:
            self.metrics = (
                "correctness",
                "faithfulness",
                "context_recall",
                "rouge_l",
                "official_accuracy",
            )
            self.judge_calls_per_question = (
                _CORRECTNESS_CALLS
                + _FAITHFULNESS_CALLS
                + _CONTEXT_RECALL_CALLS
                + _ACCURACY_CALLS
            )
        else:
            self.metrics = ("correctness", "rouge_l", "official_accuracy")
            self.judge_calls_per_question = _CORRECTNESS_CALLS + _ACCURACY_CALLS

    def _embed(self) -> Embedder:
        if self._embedder is None:
            self._embedder = SentenceTransformerEmbedder()
        return self._embedder

    async def grade(
        self, question: BenchmarkQuestion, answer: SystemAnswer, judge: ChatModelJudge
    ) -> Grade:
        """Score one answer."""
        gold = question.reference["answer"]
        evidence = "\n".join(question.reference["evidence"])
        quality = await answer_quality(
            judge,
            question,
            answer,
            gold,
            names=tuple(
                m for m in self.metrics if m in ("correctness", "faithfulness")
            ),
        )
        recall = (
            await answer_quality(
                judge, question, answer, evidence, names=("context_recall",)
            )
            if "context_recall" in self.metrics
            else {}
        )
        accuracy, parse_error = await answer_accuracy(
            judge, self._embed(), question.query, answer.text, gold
        )
        return Grade(
            scores={
                **quality,
                **recall,
                "rouge_l": rouge_l(answer.text, gold),
                "official_accuracy": accuracy,
            },
            flags=["parse_error"] if parse_error else [],
        )
