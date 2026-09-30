"""Character-span precision and recall for LegalBench-RAG, plus judged correctness.

The span formulas follow the benchmark's own scorer. A question has gold spans in
one or more documents. Precision is the share of the retrieved characters that lie
in a gold span. Recall is the share of the gold characters that a retrieved span
covers. Spans match by document path and half-open overlap.

The benchmark scores a fixed number of retrieved snippets. Here the retrieved
snippets are the chunks the agent cites, so the scores do not compare with
published precision at k.
"""

import unicodedata
from collections.abc import Iterable, Sequence

from agrag.eval import ChatModelJudge
from benchmarks.grading.base import Grade, Grader, answer_quality
from benchmarks.models import BenchmarkQuestion
from benchmarks.systems.base import CitedChunk, SystemAnswer


Span = tuple[str, int, int]


def _nfc(path: str) -> str:
    return unicodedata.normalize("NFC", path)


def _spans(chunks: Iterable[CitedChunk]) -> list[Span]:
    """Return the distinct spans of the chunks that have offsets."""
    found = {
        (_nfc(c.uri), c.char_start, c.char_end)
        for c in chunks
        if c.char_start is not None and c.char_end is not None
    }
    return sorted(found)  # type: ignore[arg-type]


def _overlap(retrieved: Span, gold: Span) -> int:
    """Return the characters two spans share, or 0 in another document."""
    if retrieved[0] != gold[0]:
        return 0
    return max(0, min(retrieved[2], gold[2]) - max(retrieved[1], gold[1]))


def precision_recall(
    retrieved: Sequence[Span], gold: Sequence[Span]
) -> tuple[float, float]:
    """Score retrieved spans against gold spans that do not overlap each other.

    Args:
        retrieved: ``(path, start, end)`` of each retrieved snippet.
        gold: ``(path, start, end)`` of each gold snippet.

    Returns:
        Precision and recall. Each is 0 when its denominator is 0.
    """
    hit = sum(_overlap(r, g) for r in retrieved for g in gold)
    retrieved_length = sum(end - start for _, start, end in retrieved)
    gold_length = sum(end - start for _, start, end in gold)
    return (
        hit / retrieved_length if retrieved_length else 0.0,
        hit / gold_length if gold_length else 0.0,
    )


class LegalGrader(Grader):
    """Span precision and recall of the cited chunks, and judged correctness.

    The primary scores use the chunks the answer cites. The expanded scores add
    the chunks that the cited entities and relations were extracted from. A
    question with no chunk citation scores 0 on all four and gets the flag
    ``no_chunk_citation``. ``non_chunk_citation_share`` is the share of citations
    that are not chunks.
    """

    metrics = (
        "precision",
        "recall",
        "expanded_precision",
        "expanded_recall",
        "correctness",
        "non_chunk_citation_share",
    )
    judge_calls_per_question = 1

    async def grade(
        self, question: BenchmarkQuestion, answer: SystemAnswer, judge: ChatModelJudge
    ) -> Grade:
        """Score one answer."""
        snippets = question.reference["snippets"]
        gold = [(_nfc(s["uri"]), *s["span"]) for s in snippets]
        primary = _spans(answer.cited_chunks)
        expanded = _spans([*answer.cited_chunks, *answer.source_chunks])
        precision, recall = precision_recall(primary, gold)
        expanded_precision, expanded_recall = precision_recall(expanded, gold)
        cited = len(answer.cited_chunks) + answer.non_chunk_citations
        quality = await answer_quality(
            judge,
            question,
            answer,
            reference="\n".join(s["answer"] for s in snippets),
        )
        return Grade(
            scores={
                "precision": precision,
                "recall": recall,
                "expanded_precision": expanded_precision,
                "expanded_recall": expanded_recall,
                "correctness": quality["correctness"],
                "non_chunk_citation_share": (
                    answer.non_chunk_citations / cited if cited else 0.0
                ),
            },
            flags=[] if primary else ["no_chunk_citation"],
        )
