"""The GraphRAG-Bench answer accuracy metric, ported from its scorer.

The metric is 0.75 times an F1 over atomic statements, judged by a model, plus 0.25
times the similarity of the answer and reference embeddings. It is ported from
``Evaluation/metrics/answer_accuracy.py`` of
https://github.com/GraphRAG-Bench/GraphRAG-Benchmark at commit
``fdbab5959b18c96532580877ffe27d112bccc0ec``. The prompts and the arithmetic are
kept. These parts differ:

- The judge is the benchmark's judge model, not the scorer's OpenAI client.
- The embedder is the run's embedder, not BGE, so the similarity term does not
  compare with published numbers.
- The judge reply may be wrapped in a code fence. The fence is removed before the
  JSON parse. A reply that still does not parse takes the scorer's fallback (no
  statements, or an F1 of 0), and the question gets the flag ``parse_error``.

The upstream license, which covers the ported prompts and code:

    MIT License

    Copyright (c) 2025 XMU-DeepLIT

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
"""

import asyncio
import json
import math

from pydantic import BaseModel, ValidationError

from agrag.embedding.base import Embedder
from agrag.eval import ChatModelJudge


WEIGHTS = (0.75, 0.25)


class StatementsWithReason(BaseModel):
    """A statement and why the judge put it in its class."""

    statement: str
    reason: str


class ClassificationWithReason(BaseModel):
    """The judge's split of statements into true positives, false positives, misses."""

    TP: list[StatementsWithReason]
    FP: list[StatementsWithReason]
    FN: list[StatementsWithReason]


STATEMENT_GENERATOR_PROMPT = """
Generate concise independent statements from the given text that represent factual claims.
Respond ONLY with a JSON array of strings. Do not include any other text.

Example Input:
"The sun is powered by nuclear fusion. This process creates light and heat."

Example Output:
["The sun is powered by nuclear fusion", "Nuclear fusion creates light and heat"]

Input Text:
{text}

Generated Statements:
"""  # noqa: E501, W291

CORRECTNESS_PROMPT_TEMPLATE = """
Analyze statements from an answer compared to ground truth. Classify each as:
- TP (True Positive): Present in answer and supported by ground truth
- FP (False Positive): Present in answer but unsupported
- FN (False Negative): Missing from answer but present in ground truth

Provide JSON output with lists of TP, FP, FN objects containing 'statement' and 'reason'.

Examples:
{examples}

Current Analysis:
Question: "{question}"
Answer Statements: {answer}
Ground Truth Statements: {ground_truth}
"""  # noqa: E501

CORRECTNESS_EXAMPLES = [
    {
        "input": {
            "question": "What powers the sun and its primary function?",
            "answer": [
                "The sun is powered by nuclear fission",
                "Its primary function is providing light",
            ],
            "ground_truth": [
                "The sun is powered by nuclear fusion",
                "Fusion creates energy for heat and light",
                "Sunlight is essential for Earth's climate",
            ],
        },
        "output": {
            "TP": [
                {
                    "statement": "Its primary function is providing light",
                    "reason": "Matches ground truth about light",
                }
            ],
            "FP": [
                {
                    "statement": "The sun is powered by nuclear fission",
                    "reason": "Contradicts fusion fact",
                }
            ],
            "FN": [
                {
                    "statement": "The sun is powered by nuclear fusion",
                    "reason": "Missing correct power source",
                },
                {
                    "statement": "Fusion creates energy for heat and light",
                    "reason": "Missing energy creation detail",
                },
            ],
        },
    }
]


def fbeta_score(tp: int, fp: int, fn: int, beta: float = 1.0) -> float:
    """Return the F-beta score of statement counts, with the scorer's smoothing.

    Args:
        tp: The number of true positives.
        fp: The number of false positives.
        fn: The number of false negatives.
        beta: The weight of recall against precision. 1 gives the F1 score.

    Returns:
        The F-beta score from 0 to 1.
    """
    precision = tp / (tp + fp + 1e-10)
    recall = tp / (tp + fn + 1e-10)
    return (
        (1 + beta**2) * (precision * recall) / ((beta**2 * precision) + recall + 1e-10)
    )


def parse_json(reply: str) -> object:
    """Parse a judge reply as JSON, after removing a code fence around it.

    Args:
        reply: The text of the judge reply.

    Returns:
        The parsed JSON value.

    Raises:
        json.JSONDecodeError: The reply is not JSON.
    """
    text = reply.strip()
    if text.startswith("```"):
        text = text.partition("\n")[2].rpartition("```")[0]
    return json.loads(text)


async def _statements(judge: ChatModelJudge, text: str) -> list[str] | None:
    """Return the atomic statements of a text, or None when the reply is not a list."""
    reply = await judge.a_generate(STATEMENT_GENERATOR_PROMPT.format(text=text))
    try:
        parsed = parse_json(reply)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, list) and all(isinstance(s, str) for s in parsed):
        return parsed
    return None


async def _factuality(
    judge: ChatModelJudge,
    question: str,
    answer_statements: list[str],
    truth_statements: list[str],
) -> float | None:
    """Return the F1 of the judge's statement classes, or None on a bad reply."""
    if not answer_statements and not truth_statements:
        return 1.0
    examples = "\n".join(
        f"Input: {json.dumps(example['input'])}\n"
        f"Output: {json.dumps(example['output'])}"
        for example in CORRECTNESS_EXAMPLES
    )
    reply = await judge.a_generate(
        CORRECTNESS_PROMPT_TEMPLATE.format(
            examples=examples,
            question=question,
            answer=json.dumps(answer_statements),
            ground_truth=json.dumps(truth_statements),
        )
    )
    try:
        classes = ClassificationWithReason.model_validate(parse_json(reply))
    except (json.JSONDecodeError, ValidationError):
        return None
    return fbeta_score(len(classes.TP), len(classes.FP), len(classes.FN))


async def _similarity(embedder: Embedder, answer: str, reference: str) -> float:
    """Return the cosine similarity of two texts, scaled from -1..1 to 0..1."""
    a, b = await embedder.embed([answer, reference])
    norms = math.hypot(*a) * math.hypot(*b)
    if not norms:
        return 0.0
    return (sum(x * y for x, y in zip(a, b, strict=True)) / norms + 1) / 2


async def answer_accuracy(
    judge: ChatModelJudge,
    embedder: Embedder,
    question: str,
    answer: str,
    reference: str,
) -> tuple[float, bool]:
    """Score an answer against the reference answer.

    Args:
        judge: The judge model.
        embedder: The embedder for the similarity term.
        question: The question text.
        answer: The answer to score.
        reference: The reference answer.

    Returns:
        The score from 0 to 1, and whether a judge reply did not parse.
    """
    answer_statements, truth_statements = await asyncio.gather(
        _statements(judge, answer), _statements(judge, reference)
    )
    failed = answer_statements is None or truth_statements is None
    factuality = (
        None
        if answer_statements is None or truth_statements is None
        else await _factuality(judge, question, answer_statements, truth_statements)
    )
    failed = failed or factuality is None
    similarity = await _similarity(embedder, answer, reference)
    score = WEIGHTS[0] * (factuality or 0.0) + WEIGHTS[1] * similarity
    return score, failed
