"""End-to-end agent trajectory evaluation on the tiny corpus.

Runs the real agent on 5 handpicked questions about the invented company
corpus, traces each run with ``SpanCapture``, and scores every run with the
five trajectory metrics: the three structural rules and the two judged
metrics. The gate is the pass rate of each rule over the 5 runs and the mean
of each judged score.

It runs after merges and weekly through ``make test-eval-trajectory``, not on
pull requests. The report goes to ``reports/eval/agent_trajectory.json``, or
to the directory in ``E2E_ARTIFACT_DIR``. It holds the pass rates, the judged
means, and the per-question scores with the rule reasons on failure.

Retrieval here uses hashed word overlap, not a real embedder, so the tool the
agent picks follows lexical match. Entity-named questions resolve through
``look_up_entity``; the designer question resolves through
``explore_related``. The scores guard against regression. They do not compare
with scores from a real embedder.

Each threshold is the lowest of three baseline runs minus 0.05, rounded down
to 0.05. The first two runs used a uniform ``["task", "look_up_entity"]``
expectation; their ``expected_tools`` pass rates below are rescored under the
final per-question expectations, under which all three runs pass every
question. Baseline pass rates (rules) and means (judged):

    verifier_before_answer   1.0  1.0  1.0
    retry_budget              1.0  1.0  1.0
    expected_tools            1.0  1.0  1.0
    task_completion           1.0  1.0  1.0
    trajectory_quality        1.0  1.0  1.0

Each run made 6 to 10 LLM calls in these runs. The judged metrics add 6 judge
calls per run.
"""

import asyncio
import os
import statistics
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from agrag.eval import (
    ChatModelJudge,
    SpanCapture,
    expected_tools_metric,
    final_answer,
    retry_budget_metric,
    task_completion,
    trajectory_case,
    trajectory_quality,
    verifier_before_answer_metric,
)
from tests.integration.e2e._artifact import write_artifact


QUESTIONS = (
    {
        "id": "founder",
        "question": "Who founded Zephyra Robotics in Halvorn?",
        "expected_tools": ["task", "look_up_entity"],
    },
    {
        "id": "joined",
        "question": "When did Tobias Renn join Zephyra Robotics as chief engineer?",
        "expected_tools": ["task", "look_up_entity"],
    },
    {
        "id": "designer",
        "question": "Who designed the Lumen-9 lifting arm?",
        "expected_tools": ["task", "explore_related"],
    },
    {
        "id": "lift",
        "question": "How much weight can the Lumen-9 warehouse robot lift?",
        "expected_tools": ["task", "look_up_entity"],
    },
    {
        "id": "released",
        "question": "When did Zephyra Robotics release the Lumen-9?",
        "expected_tools": ["task", "look_up_entity"],
    },
)

THRESHOLDS = {
    "verifier_before_answer": 0.95,
    "retry_budget": 0.95,
    "expected_tools": 0.95,
    "task_completion": 0.95,
    "trajectory_quality": 0.95,
}

_REPORT_DIR = Path(__file__).resolve().parents[3] / "reports" / "eval"
_RULES = ("verifier_before_answer", "retry_budget", "expected_tools")
_JUDGED = ("task_completion", "trajectory_quality")


async def _score(
    judge: ChatModelJudge, case: LLMTestCase, expected_tools: list[str]
) -> dict[str, dict[str, Any]]:
    """Score one run with every trajectory metric, at once."""
    metrics: dict[str, BaseMetric] = {
        "verifier_before_answer": verifier_before_answer_metric(),
        "retry_budget": retry_budget_metric(3),
        "expected_tools": expected_tools_metric(expected_tools),
        "task_completion": task_completion(judge),
        "trajectory_quality": trajectory_quality(judge),
    }
    await asyncio.gather(*(metric.a_measure(case) for metric in metrics.values()))
    return {
        name: {
            "score": metric.score,
            "reason": metric.reason,
            "breakdown": getattr(metric, "score_breakdown", {}),
        }
        for name, metric in metrics.items()
    }


async def test_agent_trajectory_meets_thresholds(
    judge: ChatModelJudge,
    agent_factory: Callable[..., Any],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each rule's pass rate and each judged mean is at or above its threshold."""
    rows: list[dict[str, Any]] = []
    started = time.monotonic()
    for item in QUESTIONS:
        with SpanCapture() as capture:
            agent = agent_factory(capture.tracer)
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": item["question"]}]}
            )
        trajectory = capture.trajectory()
        answer = final_answer(result)
        case = trajectory_case(item["question"], answer, trajectory)
        with capsys.disabled():
            print(
                f"\n[{time.monotonic() - started:5.0f}s] answered {item['id']}",
                flush=True,
            )
        rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "answer": answer,
                "agent_llm_calls": sum(
                    1 for step in trajectory.steps if step.kind == "llm"
                ),
                "tool_calls": [
                    step.name for step in trajectory.steps if step.kind == "tool"
                ],
                "scores": await _score(judge, case, list(item["expected_tools"])),
            }
        )
        with capsys.disabled():
            print(
                f"[{time.monotonic() - started:5.0f}s] scored {item['id']}", flush=True
            )
    pass_rates = {
        name: statistics.mean(row["scores"][name]["score"] for row in rows)
        for name in _RULES
    }
    means = {
        name: statistics.mean(row["scores"][name]["score"] for row in rows)
        for name in _JUDGED
    }
    if "E2E_ARTIFACT_DIR" not in os.environ:
        monkeypatch.setenv("E2E_ARTIFACT_DIR", str(_REPORT_DIR))
    report = write_artifact(
        "agent_trajectory",
        {"pass_rates": pass_rates, "means": means, "questions": rows},
    )

    assert len(report["questions"]) == len(QUESTIONS)
    gated = {**pass_rates, **means}
    below = {
        name: (score, THRESHOLDS[name])
        for name, score in gated.items()
        if score < THRESHOLDS[name]
    }
    assert not below, f"scores below their thresholds (value, threshold): {below}"
