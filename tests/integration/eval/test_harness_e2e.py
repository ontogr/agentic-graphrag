"""Smoke test for the evaluation harness.

Runs the real agent over the tiny corpus and scores its answer with a
median-of-3 ``GEval`` from the real judge. It checks that the pieces connect,
not the answer quality: the score only has to fall in ``[0, 1]``. The judge
and the agent model ids print to the log so a run shows what graded what.
"""

from collections.abc import Callable
from typing import Any

import pytest
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

from agrag.agents.settings import AgentLLMSettings
from agrag.eval.judge import ChatModelJudge
from agrag.eval.repeat import MedianOfN


QUESTION = "Who designed the Lumen-9 lifting arm at Zephyra Robotics?"
EXPECTED = "Tobias Renn designed the Lumen-9 lifting arm."


def _answer_text(result: dict[str, Any]) -> str:
    """Return the text of the last message in an agent result."""
    last = result["messages"][-1]
    return last["content"] if isinstance(last, dict) else last.content


async def test_agent_answer_scores_in_unit_range(
    judge: ChatModelJudge,
    agent_factory: Callable[[], Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A real agent answer gets a median-of-3 GEval score between 0 and 1."""
    agent = agent_factory()
    result = await agent.ainvoke({"messages": [{"role": "user", "content": QUESTION}]})
    metric = MedianOfN(
        GEval(
            name="Correctness",
            criteria=(
                "Check whether the actual output states the same fact as the "
                "expected output. Penalize contradictions and missing facts."
            ),
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.EXPECTED_OUTPUT,
            ],
            model=judge,
            async_mode=False,
        ),
        n=3,
    )

    await metric.a_measure(
        LLMTestCase(
            input=QUESTION,
            actual_output=_answer_text(result),
            expected_output=EXPECTED,
        )
    )

    with capsys.disabled():
        agent_model = AgentLLMSettings.from_openai_compatible_env().clients[0].model
        print(f"\nagent model: {agent_model}")
        print(f"judge model: {judge.get_model_name()}")
        print(f"eval score: {metric.score}")
    assert metric.score is not None
    assert 0.0 <= metric.score <= 1.0
