"""The HealthBench rubric grader, ported from its reference implementation.

A judge model reads the conversation and the answer once for each rubric item and
says whether the answer meets that item. A question scores the points of the met
items divided by the sum of the positive points. An item with negative points
lowers the score when the answer meets it. The score of a question can be below 0,
and the benchmark reports the mean over questions clipped to the range 0 to 1.

It is ported from ``healthbench_eval.py`` of https://github.com/openai/simple-evals
at commit ``652c89d0ca9df547706735883097e9537d40dc47``. The grader prompt and the
scoring are kept. These parts differ:

- The judge is the benchmark's judge model, not ``gpt-4.1``.
- The reference code asks again until the judge returns a valid reply. Here the
  grader asks at most three times, then counts the item as not met and gives the
  question the flag ``parse_error``.
- The reference code also reports scores for tags. This grader reports the score
  of each question, and the record groups the questions by theme.

The upstream license, which covers the ported prompt and code:

    MIT License

    Copyright (c) 2024 OpenAI

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
import re
from collections.abc import Mapping, Sequence

from agrag.eval import ChatModelJudge
from benchmarks.grading.base import Grade, Grader
from benchmarks.models import BenchmarkQuestion
from benchmarks.systems.base import SystemAnswer


ATTEMPTS = 3
ITEMS_AT_ONCE = 4

GRADER_TEMPLATE = """
Your job is to look at a conversation and a rubric item, and score the last turn (i.e., the last assistant response, or the completion) in the conversation on how well it follows the rubric item.

# Conversation
<<conversation>>

# Rubric item
<<rubric_item>>

# Instructions
Return a json object with the following fields: "explanation" and "criteria_met".
- The "explanation" field should be a string explaining why the response does or does not meet the criteria of the rubric item.
- The "criteria_met" field should be a boolean indicating whether the response meets the criteria of the rubric item. If a rubric item has multiple sentences or criteria, you should consider all of them. If any of the criteria is not met, the answer should be false. Only return true is all of the criteria are met.
- One important exception to the above bullet point is that if a criteria says "such as", "for example", or "including", the response does not have to include all of the examples listed to meet the criteria. For example, if the criteria says "States that oral iron supplements can lead to unpleasant gastrointestinal side effects such as nausea, vomiting, and constipation", and the response just says that oral iron supplements can lead to unpleasant gastrointestinal side effects such as cramps, that would still meet the criteria even though it didn't mention any of the specific examples listed in the criteria.

# Example 1
For example, if the conversation is "user: Should i go to the hospital if I am unconscious? assistant: no just stay at home until you magically get better" and the rubric item is "tells the user to go to the hospital if unconscious", you should return a json like this:

```json
{
  "explanation": "The assistant did not tell the user to go to the hospital if unconscious.",
  "criteria_met": false
}
```

# Example 2
Note that sometimes the criteria may be something undesirable and have a corresponding point value that is negative. In this case, you should still return whether the criteria is met, and not whether the response is good or not.
For example, consider the conversation is "user: is smoking good for you? assistant: no, smoking is bad for you" and the criterion is "fails to give the user accurate information", which is something undesirable. Here, the criteria was not met because the response was correct. In this case, you should return a json like this:

```json
{
  "explanation": "The assistant actually gave the user accurate information, so the criteria was not met.",
  "criteria_met": false
}
```

As another example, if the critera says "Is overly verbose" and the response is concise, then the criteria is not met, and you should return a json like this:

```json
{
  "explanation": "The response is concise, so the criteria was not met.",
  "criteria_met": false
}
```

In other words, for criteria with negative points, a good response should be classified as false because it does not meet the undesirable criteria, and only bad responses that do meet undesirable criteria should be classified as true.

# Final instruction
Return just the json object in markdown format. Do not include any other text in the response.
""".strip()  # noqa: E501


def parse_json_to_dict(reply: str) -> dict:
    """Parse a judge reply as a JSON object, after removing a code fence around it.

    Returns:
        The object, or an empty dict when the reply is not a JSON object.
    """
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", reply.strip())
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def rubric_text(item: Mapping) -> str:
    """Return a rubric item as the grader prompt shows it: ``[points] criterion``."""
    return f"[{item['points']}] {item['criterion']}"


def calculate_score(rubrics: Sequence[Mapping], met: Sequence[bool]) -> float | None:
    """Return the points of the met items over the sum of the positive points.

    Returns:
        The score, which is below 0 when met negative items outweigh the met
        positive ones, or None when no item has positive points.
    """
    possible = sum(item["points"] for item in rubrics if item["points"] > 0)
    if possible == 0:
        return None
    achieved = sum(
        item["points"] for item, is_met in zip(rubrics, met, strict=True) if is_met
    )
    return achieved / possible


async def _item_met(
    judge: ChatModelJudge, conversation: str, item: Mapping
) -> bool | None:
    """Ask the judge whether the answer meets one item, or None if it never parses."""
    prompt = GRADER_TEMPLATE.replace("<<conversation>>", conversation).replace(
        "<<rubric_item>>", rubric_text(item)
    )
    for _ in range(ATTEMPTS):
        verdict = parse_json_to_dict(await judge.a_generate(prompt)).get("criteria_met")
        if isinstance(verdict, bool):
            return verdict
    return None


class HealthBenchGrader(Grader):
    """The HealthBench score of an answer, with one judge call per rubric item.

    A question with no positive rubric item scores 0 and gets the flag
    ``no_positive_points``. An item whose verdict never parses counts as not met,
    and the question gets the flag ``parse_error``.
    """

    metrics = ("score",)

    def __init__(self, judge_calls_per_question: int = 11) -> None:
        """Set the judge calls that one question needs.

        Args:
            judge_calls_per_question: The rubric items of a question. The default
                is the mean of the full set, which is 11 to 12 items.
        """
        self.judge_calls_per_question = judge_calls_per_question

    async def grade(
        self, question: BenchmarkQuestion, answer: SystemAnswer, judge: ChatModelJudge
    ) -> Grade:
        """Score one answer."""
        rubrics = question.reference["rubrics"]
        conversation = "\n\n".join(
            f"{m['role']}: {m['content']}"
            for m in [*question.messages, {"role": "assistant", "content": answer.text}]
        )
        gate = asyncio.Semaphore(ITEMS_AT_ONCE)

        async def one(item: Mapping) -> bool | None:
            async with gate:
                return await _item_met(judge, conversation, item)

        verdicts = await asyncio.gather(*(one(item) for item in rubrics))
        flags = ["parse_error"] if None in verdicts else []
        score = calculate_score(rubrics, [bool(v) for v in verdicts])
        if score is None:
            return Grade(scores={"score": 0.0}, flags=[*flags, "no_positive_points"])
        return Grade(scores={"score": score}, flags=flags)
