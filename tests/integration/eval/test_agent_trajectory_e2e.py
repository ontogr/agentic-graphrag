"""End-to-end agent trajectory evaluation on the tiny corpus.

Runs the real agent on 5 handpicked questions about the invented company
corpus, traces each run with ``SpanCapture``, and scores every run with three
trajectory metrics: the expected-tools rule and the two judged metrics. The
gate is the pass rate of the rule over the 5 runs and the mean of each judged
score.

It runs after merges and weekly through ``make test-eval-trajectory``, not on
pull requests. The report goes to ``reports/eval/agent_trajectory.json``, or
to the directory in ``E2E_ARTIFACT_DIR``. It holds the pass rates, the judged
means, and the per-question scores with the rule reasons on failure.

Retrieval here uses hashed word overlap, not a real embedder, so the tool the
agent picks follows lexical match. The scores guard against regression. They
do not compare with scores from a real embedder.

The thresholds are not yet baselined against the single task agent. Re-run
this test with the real LLM and set them from the measured runs.
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
    task_completion,
    trajectory_case,
    trajectory_quality,
)
from tests.integration.e2e._artifact import write_artifact


QUESTIONS = (
    {
        "id": "founder",
        "question": "Who founded Zephyra Robotics in Halvorn?",
        "expected_tools": ["search_evidence", "fetch_evidence"],
    },
    {
        "id": "joined",
        "question": "When did Tobias Renn join Zephyra Robotics as chief engineer?",
        "expected_tools": ["search_evidence", "fetch_evidence"],
    },
    {
        "id": "designer",
        "question": "Who designed the Lumen-9 lifting arm?",
        "expected_tools": ["search_evidence", "fetch_evidence"],
    },
    {
        "id": "lift",
        "question": "How much weight can the Lumen-9 warehouse robot lift?",
        "expected_tools": ["search_evidence", "fetch_evidence"],
    },
    {
        "id": "released",
        "question": "When did Zephyra Robotics release the Lumen-9?",
        "expected_tools": ["search_evidence", "fetch_evidence"],
    },
)

THRESHOLDS = {
    "expected_tools": 0.85,
    "task_completion": 0.85,
    "trajectory_quality": 0.85,
}

_REPORT_DIR = Path(__file__).resolve().parents[3] / "reports" / "eval"
_RULES = ("expected_tools",)
_JUDGED = ("task_completion", "trajectory_quality")


async def _score(
    judge: ChatModelJudge, case: LLMTestCase, expected_tools: list[str]
) -> dict[str, dict[str, Any]]:
    """Score one run with every trajectory metric, at once."""
    metrics: dict[str, BaseMetric] = {
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
                {"task_name": item["id"], "question": item["question"]}
            )
        trajectory = capture.trajectory()
        answer = result["answer"]
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
