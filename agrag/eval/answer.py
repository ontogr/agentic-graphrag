"""Answer-quality metrics for agrag, scored from questions and reference answers.

``answer_case`` turns one agent run into a DeepEval test case. The four factories
build DeepEval metrics that run the judge once. ``CitationAccuracyMetric`` checks
each cited sentence against the evidence its citation keys point to.

All metrics judge against the evidence text the agent saw, as ``Ledger.render``
shows it. A chunk shows in full up to 2000 characters, so a claim that needs text past
that point counts as unsupported.
"""

import asyncio
import re
from typing import Any

from deepeval.metrics import (
    BaseMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    FaithfulnessMetric,
    GEval,
)
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, SingleTurnParams

from agrag.agents.result import AgentRunResult


ABSTENTION = "No relevant evidence found."

_KEY = r"[EGRCVX]\d+"
_KEY_TOKEN = re.compile(rf"\b{_KEY}\b")
_KEY_GROUP = re.compile(rf"[\[(]\s*{_KEY}(?:\s*[,;]\s*{_KEY})*\s*[\])]")
_BRACKETED = re.compile(r"[\[(][^\[\]()]*[\])]")
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[(])")
_ABBREVIATIONS = frozenset(
    {"U.S.", "Inc.", "Corp.", "Co.", "Ltd.", "No.", "vs.", "e.g.", "i.e."}
)
_MIN_WORDS = 4
_MAX_CONCURRENT_JUDGE_CALLS = 8

_CORRECTNESS_STEPS = [
    "Find facts in the actual output that contradict the expected output. A "
    "contradiction lowers the score sharply.",
    "Penalize the omission of details that the expected output states.",
    "Do not penalize extra detail in the actual output that does not contradict "
    "the expected output.",
    "Treat numbers as equal when they agree after rounding to the precision the "
    "expected output states and after unit conversion. For example, $1.2 billion "
    "equals $1,200 million.",
    "Accept vague wording and a differing opinion when the facts agree.",
]
_SUPPORT_STEPS = [
    "List each figure and entity that the actual output states.",
    "For a figure that the retrieval context does not state, do the calculation "
    "yourself from the figures it does state (sum, difference, ratio, percent "
    "change). Count the figure as supported when your result matches it after "
    "rounding.",
    "Lower the score for each figure or entity that the retrieval context does "
    "not state and that no such calculation gives.",
]


def _content_text(content: Any) -> str:
    """Join the text of a message that holds a string or a list of blocks."""
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def _is_assistant(message: Any) -> bool:
    """Tell an assistant message from a dict or a LangChain message object."""
    if isinstance(message, dict):
        return message.get("role") == "assistant"
    return getattr(message, "type", None) == "ai"


def final_answer(result: AgentRunResult) -> str:
    """Return the text of the last assistant message in an agent run.

    Handles message dicts and LangChain message objects, and content that is a
    string or a list of blocks. Only text blocks count.

    Args:
        result: The result of ``agent.ainvoke``.

    Raises:
        ValueError: The run holds no assistant message.
    """
    for message in reversed(result["messages"]):
        if _is_assistant(message):
            content = (
                message["content"] if isinstance(message, dict) else message.content
            )
            return _content_text(content)
    raise ValueError("agent result has no assistant message")


def _rendered_evidence(result: AgentRunResult) -> dict[str, str]:
    """Return each ledger key with the text the agent saw for it, in key order."""
    ledger = result["ledger"]
    evidence = {}
    for key in ledger.keys:
        found = ledger.resolve(key)
        if found is not None:
            evidence[key] = ledger.render(found)
    return evidence


def answer_case(question: str, result: AgentRunResult, reference: str) -> LLMTestCase:
    """Build the test case that every answer-quality metric scores.

    ``retrieval_context`` holds the evidence the agent saw, as the ledger
    rendered it, in key order. ``metadata["citations"]`` maps each
    key to that text for ``CitationAccuracyMetric``.

    Args:
        question: The question the agent answered.
        result: The result of ``agent.ainvoke`` for that question.
        reference: The reference answer.
    """
    evidence = _rendered_evidence(result)
    return LLMTestCase(
        input=question,
        actual_output=final_answer(result),
        expected_output=reference,
        retrieval_context=list(evidence.values()),
        metadata={"citations": evidence},
    )


def correctness(judge: DeepEvalBaseLLM, *, threshold: float = 0.5) -> BaseMetric:
    """Build the answer correctness metric against the reference.

    Args:
        judge: The judge model.
        threshold: The minimum score that counts as success.
    """
    return GEval(
        name="Correctness",
        evaluation_steps=_CORRECTNESS_STEPS,
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
        ],
        model=judge,
        threshold=threshold,
    )


def faithfulness(judge: DeepEvalBaseLLM, *, threshold: float = 0.5) -> BaseMetric:
    """Build the metric for claims that the evidence the agent saw does not contradict.

    A claim that the evidence does not mention counts as faithful. Only a claim
    that the evidence contradicts lowers the score. ``CitationAccuracyMetric``
    catches unsupported claims. Takes the same arguments as ``correctness``.
    """
    return FaithfulnessMetric(model=judge, threshold=threshold)


def context_precision(judge: DeepEvalBaseLLM, *, threshold: float = 0.5) -> BaseMetric:
    """Build the metric for useful evidence ranked before noise.

    Takes the same arguments as ``correctness``.
    """
    return ContextualPrecisionMetric(model=judge, threshold=threshold)


def context_recall(judge: DeepEvalBaseLLM, *, threshold: float = 0.5) -> BaseMetric:
    """Build the metric for reference facts that the evidence covers.

    Takes the same arguments as ``correctness``.
    """
    return ContextualRecallMetric(model=judge, threshold=threshold)


def _join_abbreviations(pieces: list[str]) -> list[str]:
    """Rejoin pieces that a split cut after an abbreviation."""
    sentences: list[str] = []
    for piece in pieces:
        if sentences and sentences[-1].split()[-1] in _ABBREVIATIONS:
            sentences[-1] = f"{sentences[-1]} {piece}"
        else:
            sentences.append(piece)
    return sentences


def _split_sentences(text: str) -> list[str]:
    """Split an answer into sentences, one per bullet line at the least.

    A sentence that ends in an abbreviation and starts the next word with a
    capital letter stays joined to that word.
    """
    sentences: list[str] = []
    for raw_line in text.splitlines():
        line = _BULLET.sub("", raw_line).strip()
        if line:
            sentences.extend(_join_abbreviations(_SENTENCE_BREAK.split(line)))
    return sentences


def _citations(sentence: str, known: set[str]) -> tuple[list[str], bool]:
    """Return the keys a sentence cites and whether any is fabricated.

    A token that looks like a key counts as a citation when it is a known key or
    sits inside brackets or parentheses. A bracketed key that is not known is
    fabricated.
    """
    bracketed = [m.span() for m in _BRACKETED.finditer(sentence)]
    keys: list[str] = []
    fabricated = False
    for match in _KEY_TOKEN.finditer(sentence):
        key = match.group()
        inside = any(start <= match.start() < end for start, end in bracketed)
        if key in known:
            keys.append(key)
        elif inside:
            fabricated = True
    return list(dict.fromkeys(keys)), fabricated


def _without_keys(sentence: str, known: set[str]) -> str:
    """Return the sentence with its citation keys removed."""
    text = _KEY_GROUP.sub("", sentence)
    text = _KEY_TOKEN.sub(lambda m: "" if m.group() in known else m.group(), text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def _support_metric(judge: DeepEvalBaseLLM, threshold: float) -> BaseMetric:
    """Build the check that the evidence supports one sentence."""
    return GEval(
        name="Citation support",
        evaluation_steps=_SUPPORT_STEPS,
        evaluation_params=[
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.RETRIEVAL_CONTEXT,
        ],
        model=judge,
        threshold=threshold,
        async_mode=False,
    )


class _CitedSentence:
    """One sentence with the evidence it cites, ready to judge."""

    def __init__(self, text: str, evidence: list[str], fabricated: bool) -> None:
        self.text = text
        self.evidence = evidence
        self.fabricated = fabricated

    def case(self) -> LLMTestCase:
        """Return the test case that asks whether the evidence supports the text."""
        return LLMTestCase(
            input=self.text, actual_output=self.text, retrieval_context=self.evidence
        )


class CitationAccuracyMetric(BaseMetric):
    """Score whether each cited sentence follows from the evidence it cites.

    The unit is the sentence. A sentence counts as cited when it carries a
    citation key. A judge decides whether the text of the cited evidence supports
    the sentence. It scores each sentence with one ``GEval`` run. A cited key that
    the run's ledger did not assign is fabricated: the sentence is unsupported and
    no judge call happens.

    The score is the F1 of two ratios. Precision is supported cited sentences
    over cited sentences. Recall is supported cited sentences over all sentences
    of at least four words, plus any shorter cited sentence. ``score_breakdown``
    holds both and the sentence counts. An answer with no citations scores 0. An
    abstention, the exact text ``No relevant evidence found.``, scores 1.

    The test case must come from ``answer_case``, which puts the evidence under
    ``metadata["citations"]``. A judge failure on any sentence raises.

    Attributes:
        judge: The judge model.
        threshold: The minimum score that counts as success, and the minimum
            support score for one sentence.
    """

    def __init__(self, judge: DeepEvalBaseLLM, *, threshold: float = 0.5) -> None:
        """Bind the judge and the threshold."""
        self.judge = judge
        self.threshold = threshold
        self._cutoff = threshold

    def measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        """Judge the cited sentences one after the other."""
        plan = self._plan(test_case)
        if not isinstance(plan, tuple):
            return plan
        cited, eligible = plan
        supported = [
            not sentence.fabricated
            and _support_metric(self.judge, self._cutoff).measure(sentence.case())
            >= self._cutoff
            for sentence in cited
        ]
        return self._finish(supported, eligible)

    async def a_measure(
        self, test_case: LLMTestCase, *args: Any, **kwargs: Any
    ) -> float:
        """Judge the cited sentences at once, at most eight judge calls at a time."""
        plan = self._plan(test_case)
        if not isinstance(plan, tuple):
            return plan
        cited, eligible = plan
        gate = asyncio.Semaphore(_MAX_CONCURRENT_JUDGE_CALLS)

        async def is_supported(sentence: _CitedSentence) -> bool:
            if sentence.fabricated:
                return False
            async with gate:
                score = await _support_metric(self.judge, self._cutoff).a_measure(
                    sentence.case()
                )
            return score >= self._cutoff

        supported = await asyncio.gather(*(is_supported(s) for s in cited))
        return self._finish(list(supported), eligible)

    @property
    def __name__(self) -> str:
        """The metric name shown in reports."""
        return "Citation Accuracy"

    def _plan(self, test_case: LLMTestCase) -> float | tuple[list[_CitedSentence], int]:
        """Split the answer into cited sentences and count the eligible ones.

        Returns the score instead when the answer is an abstention or has no
        citation, because no judge call is needed.
        """
        metadata = test_case.metadata
        if test_case.actual_output is None or metadata is None:
            raise ValueError("citation accuracy needs a case built by answer_case")
        answer = test_case.actual_output.strip()
        citations: dict[str, str] = metadata["citations"]
        known = set(citations)

        if answer == ABSTENTION:
            return self._set(1.0, "The agent abstained.", {})

        cited: list[_CitedSentence] = []
        eligible = 0
        for sentence in _split_sentences(answer):
            keys, fabricated = _citations(sentence, known)
            text = _without_keys(sentence, known)
            if keys or fabricated:
                cited.append(
                    _CitedSentence(text, [citations[key] for key in keys], fabricated)
                )
                eligible += 1
            elif len(text.split()) >= _MIN_WORDS:
                eligible += 1
        if not cited:
            return self._set(
                0.0, "The answer has no citations.", {"sentences": eligible}
            )
        return cited, eligible

    def _finish(self, supported: list[bool], eligible: int) -> float:
        """Record precision, recall and their F1 for judged sentences."""
        hits = sum(supported)
        precision = hits / len(supported)
        recall = hits / eligible
        score = 2 * precision * recall / (precision + recall) if hits else 0.0
        return self._set(
            score,
            f"{hits} of {len(supported)} cited sentences are supported.",
            {
                "citation_precision": precision,
                "citation_recall": recall,
                "cited_sentences": len(supported),
                "supported_sentences": hits,
                "sentences": eligible,
            },
        )

    def _set(self, score: float, reason: str, breakdown: dict[str, Any]) -> float:
        self.score = score
        self.reason = reason
        self.score_breakdown = breakdown
        self.success = self.is_successful()
        return score
