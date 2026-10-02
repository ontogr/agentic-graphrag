"""The BEAM scorer, ported: a rubric judge and the event-ordering score.

Ported from ``src/evaluation/compute_metrics.py`` and ``src/prompts.py`` of
https://github.com/mohammadtavakoli78/BEAM at commit
``b2da22eac88bb0874c64665f13457eb99835774a``. The judge prompt and the arithmetic of
the event-ordering score are kept. These parts differ:

- The judge is the benchmark's judge model, not the scorer's OpenAI client, and it
  takes one prompt string. The system message of the equivalence check is put at
  the start of that string.
- A judge reply inside a code fence is unwrapped, as the scorer does. A reply that
  does not parse scores 0 for its rubric item, and the question gets the flag
  ``parse_error``. The scorer tries a JSON repair library first.
- A blank line of the answer is never sent to the equivalence check. The scorer
  sends it and counts it as an unmatched line either way.
- The equivalence instruction has one spelling error fixed ("explanation").
- A rank correlation that is not a number, which happens when fewer than two items
  are ranked, counts as 0.

The upstream license, which covers the ported prompt and code:

    MIT License

    Copyright (c) 2025 Mohammad Tavakoli

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
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from scipy.stats import kendalltau

from agrag.eval import ChatModelJudge


unified_llm_judge_base_prompt = """
You are an expert evaluator tasked with judging whether the LLM's response demonstrates compliance with the specified RUBRIC CRITERION.

## EVALUATION INPUTS
- RUBRIC CRITERION (what to check): <rubric_item>
- RESPONSE TO EVALUATE: <llm_response>

## EVALUATION RUBRIC:
The rubric defines a specific requirement, constraint, or expected behavior that the LLM response should demonstrate.\x20

**IMPORTANT**: Pay careful attention to whether the rubric specifies:
- **Positive requirements** (things the response SHOULD include/do)
- **Negative constraints** (things the response SHOULD NOT include/do, often indicated by "no", "not", "avoid", "absent")

## RESPONSIVENESS REQUIREMENT
A compliant response must be **on-topic** and attempt to answer it.
- If the response does not address the QUESTION, score **0.0** and stop.
- For negative constraints, both must hold: (a) the response is responsive to the QUESTION, and (b) the prohibited element is absent.

## SEMANTIC TOLERANCE RULES:
Judge by meaning, not exact wording.
- Accept **paraphrases** and **synonyms** that preserve intent.
- **Case/punctuation/whitespace** differences must be ignored.
- **Numbers/currencies/dates** may appear in equivalent forms (e.g., “$68,000”, “68k”, “68,000 USD”, or “sixty-eight thousand dollars”). Treat them as equal when numerically equivalent.
- If the rubric expects a number or duration, prefer **normalized comparison** (extract and compare values) over string matching.

## STYLE NEUTRALITY (prevents style contamination):
Ignore tone, politeness, length, and flourish unless the rubric explicitly requires a format/structure (e.g., “itemized list”, “no citations”, “one sentence”).
- Do **not** penalize hedging, voice, or verbosity if content satisfies the rubric.
- Only evaluate format when the rubric **explicitly** mandates it.

## SCORING SCALE:
- **1.0 (Complete Compliance)**: Fully complies with the rubric criterion.
  - Positive: required element present, accurate, properly executed (allowing semantic equivalents).
  - Negative: prohibited element **absent** AND response is **responsive**.
\x20\x20
- **0.5 (Partial Compliance)**: Partially complies.
  - Positive: element present but minor inaccuracies/incomplete execution.
  - Negative: generally responsive and mostly avoids the prohibited element but with minor/edge violations.
\x20\x20
- **0.0 (No Compliance)**: Fails to comply.
  - Positive: required element missing or incorrect.
  - Negative: prohibited element present **or** response is non-responsive/evasive even if the element is absent.

## EVALUATION INSTRUCTIONS:
1. **Understand the Requirement**: Determine if the rubric is asking for something to be present (positive) or absent (negative/constraint).

2. **Parse Compound Statements**: If the rubric contains multiple elements connected by "and" or commas, evaluate whether:
   - **All elements** must be present for full compliance (1.0)
   - **Some elements** present indicates partial compliance (0.5)
   - **No elements** present indicates no compliance (0.0)
\x20\x20\x20
3. **Check Compliance**:\x20
   - For positive requirements: Look for the presence and quality of the required element
   - For negative constraints: Look for the absence of the prohibited element

4. **Assign Score**: Based on compliance with the specific rubric criterion according to the scoring scale above.

5. **Provide Reasoning**: Explain whether the rubric criterion was satisfied and justify the score.

## OUTPUT FORMAT:
Return your evaluation in JSON format with two fields:

{
   "score": [your score: 1.0, 0.5, or 0.0],
   "reason": "[detailed explanation of whether the rubric criterion was satisfied and why this justified the assigned score]"
}

NOTE: ONLY output the json object, without any explanation before or after that
"""  # noqa: E501, RUF001

EQUIVALENCE_INSTRUCTION = """
            You are a binary classifier.
            If the TWO snippets describe the SAME event/fact, reply **YES**
            Otherwise reply **NO**. No extra words.
            DO NOT provide any explanation.
        """  # noqa: W291


RUBRIC_SCORES = (0.0, 0.5, 1.0)


class JudgeReplyError(ValueError):
    """A judge reply holds no JSON object with a numeric score."""


def parse_json_response(response: str) -> object:
    """Parse a judge reply as JSON, after removing a code fence around it.

    Raises:
        JudgeReplyError: The reply holds no parseable JSON.
    """
    response = response.strip()
    if response.startswith("```"):
        match = re.search(r"```(?:json)?\s*(\[.*\]|\{.*\})\s*```", response, re.DOTALL)
        if match:
            response = match.group(1).strip()
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass
    match = re.search(r"(\{.*?\}|\[.*?\])", response, re.DOTALL)
    if not match:
        raise JudgeReplyError("no JSON in the reply")
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise JudgeReplyError(str(error)) from error


async def rubric_item_score(
    judge: ChatModelJudge, item: str, response: str
) -> float | None:
    """Score one rubric item as 0, 0.5 or 1, or return None when the reply is bad."""
    prompt = unified_llm_judge_base_prompt.replace("<rubric_item>", item).replace(
        "<llm_response>", response
    )
    reply = await judge.a_generate(prompt)
    try:
        parsed = parse_json_response(reply)
        if not isinstance(parsed, dict):
            return None
        score = float(parsed["score"])
    except (JudgeReplyError, KeyError, TypeError, ValueError):
        return None
    return score if score in RUBRIC_SCORES else None


async def rubric_score(
    judge: ChatModelJudge, rubric: Sequence[str], response: str
) -> tuple[float, bool]:
    """Score a response as the mean of its rubric item scores.

    Returns:
        The mean score, and whether a judge reply did not parse. An item with a bad
        reply scores 0.
    """
    scores = await asyncio.gather(
        *(rubric_item_score(judge, item, response) for item in rubric)
    )
    failed = any(score is None for score in scores)
    return sum(score or 0.0 for score in scores) / len(rubric), failed


async def llm_equivalence(judge: ChatModelJudge, first: str, second: str) -> bool:
    """Ask the judge whether two snippets describe the same event or fact."""
    reply = await judge.a_generate(
        f"{EQUIVALENCE_INSTRUCTION}\nFirst snippet: {first} \n\n"
        f"                       Second snippet: {second}\n"
    )
    return re.fullmatch(r"\W*yes\W*", reply, re.IGNORECASE) is not None


async def align_with_llm(
    judge: ChatModelJudge, reference: Sequence[str], system: Sequence[str]
) -> list[str]:
    """Replace each answer line by the first unused reference item it matches.

    A blank line is left as it is, without a judge call.
    """
    used: set[int] = set()
    aligned = []
    for line in system:
        matched = None
        if line.strip():
            for index, item in enumerate(reference):
                if index not in used and await llm_equivalence(judge, item, line):
                    matched = index
                    break
        if matched is None:
            aligned.append(line)
        else:
            aligned.append(reference[matched])
            used.add(matched)
    return aligned


@dataclass(frozen=True)
class OrderingScore:
    """The event-ordering score of one answer.

    Attributes:
        precision: Matched lines over answer lines.
        recall: Matched lines over reference items.
        f1: The harmonic mean of precision and recall.
        tau_norm: Kendall tau-b of the two orders, scaled to 0 to 1.
        final_score: ``tau_norm`` times ``f1``.
    """

    precision: float
    recall: float
    f1: float
    tau_norm: float
    final_score: float


def ordering_score(
    reference: Sequence[str], aligned_system: Sequence[str]
) -> OrderingScore:
    """Score an answer whose lines are already aligned to the reference items.

    Args:
        reference: The reference items, in the gold order.
        aligned_system: The answer lines. A line that matched an item holds that
            item's text.
    """
    reference = list(reference)
    system = list(aligned_system)
    tp = sum((Counter(reference) & Counter(system)).values())
    fp = len(system) - tp
    fn = len(reference) - tp
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0

    union = list(dict.fromkeys(reference + system))
    tie_rank = len(union) + 1

    def to_rank(seq: list[str]) -> list[int]:
        ranks = {item: i + 1 for i, item in enumerate(seq)}
        return [ranks.get(u, tie_rank) for u in union]

    tau_b = kendalltau(to_rank(reference), to_rank(system), variant="b").statistic
    tau_norm = 0.0 if math.isnan(tau_b) else (float(tau_b) + 1) / 2
    return OrderingScore(precision, recall, f1, tau_norm, tau_norm * f1)


async def event_ordering_score(
    judge: ChatModelJudge, reference: Sequence[str], response: str
) -> OrderingScore:
    """Score the lines of a response against the reference order with the judge."""
    aligned = await align_with_llm(judge, reference, response.split("\n"))
    return ordering_score(reference, aligned)
