"""End-to-end answer-quality evaluation on the FinQA fixture.

Ingests one FinQA page (2 handpicked questions, see
``tests/fixtures/eval/answer_quality/NOTICE``) with a fixed extractor, runs the
real agent on each question and scores every answer with the five answer-quality
metrics from the real judge. Each judged metric is the median of 3 runs. The gate
is the mean of each metric over the questions.

It runs after merges and weekly through ``make test-eval-answer``, not on pull
requests. The report goes to ``reports/eval/answer_quality.json``, or to the
directory in ``E2E_ARTIFACT_DIR``. It holds the scores, the reasons, the citation
breakdown and the number of LLM calls the agent made for each question.

Retrieval here uses hashed word overlap, not a real embedder, so scores follow
lexical match plus graph traversal. They guard against regression. They do not
compare with scores from a real embedder. The fixed extractor keeps the graph the
same on every run, so only the agent and the judge vary.

Each threshold is the lowest of three baseline means minus 0.05, rounded down to
0.05. With 2 questions a mean takes few distinct values, so the gate is coarse.
Baseline means:

    correctness         1.000  1.000  1.000
    faithfulness        1.000  0.750  1.000
    context_precision   0.509  0.504  0.670
    context_recall      1.000  1.000  1.000
    citation_accuracy   0.500  0.444  0.472

The agent made 8 to 12 LLM calls per question in these runs. With the 3 median
runs of each judged metric and the citation checks, one run of this test makes
about 100 LLM calls.
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
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.eval import (
    ChatModelJudge,
    CitationAccuracyMetric,
    answer_case,
    context_precision,
    context_recall,
    correctness,
    faithfulness,
)
from tests.integration.e2e._artifact import write_artifact
from tests.integration.eval._answer_quality import load_questions


THRESHOLDS = {
    "correctness": 0.95,
    "faithfulness": 0.70,
    "context_precision": 0.45,
    "context_recall": 0.95,
    "citation_accuracy": 0.35,
}

_REPORT_DIR = Path(__file__).resolve().parents[3] / "reports" / "eval"
_NEEDS_EVIDENCE = ("faithfulness", "context_precision", "context_recall")


def _llm_calls(exporter: InMemorySpanExporter) -> int:
    """Count the LLM spans of one traced agent run."""
    return sum(
        1
        for span in exporter.get_finished_spans()
        if (span.attributes or {}).get("openinference.span.kind") == "LLM"
    )


async def _score(judge: ChatModelJudge, case: LLMTestCase) -> dict[str, dict[str, Any]]:
    """Score one case with every metric, at once.

    An agent that read no evidence gets 0 on the metrics that judge the evidence,
    because DeepEval rejects an empty context.
    """
    metrics: dict[str, BaseMetric] = {
        "correctness": correctness(judge),
        "faithfulness": faithfulness(judge),
        "context_precision": context_precision(judge),
        "context_recall": context_recall(judge),
        "citation_accuracy": CitationAccuracyMetric(judge),
    }
    read_evidence = bool(case.retrieval_context)
    if not read_evidence:
        for name in _NEEDS_EVIDENCE:
            del metrics[name]
    await asyncio.gather(*(metric.a_measure(case) for metric in metrics.values()))
    scores = {
        name: {
            "score": metric.score,
            "reason": metric.reason,
            "breakdown": getattr(metric, "score_breakdown", {}),
        }
        for name, metric in metrics.items()
    }
    for name in _NEEDS_EVIDENCE:
        scores.setdefault(
            name,
            {"score": 0.0, "reason": "The agent read no evidence.", "breakdown": {}},
        )
    return scores


async def test_answer_quality_means_meet_thresholds(
    judge: ChatModelJudge,
    answer_quality_agent_factory: Callable[..., Any],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each metric's mean over the two questions is at or above its threshold."""
    rows: list[dict[str, Any]] = []
    started = time.monotonic()
    for item in load_questions():
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        agent = answer_quality_agent_factory(provider.get_tracer("answer-quality"))
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": item["question"]}]}
        )
        with capsys.disabled():
            print(
                f"\n[{time.monotonic() - started:5.0f}s] answered {item['id']}",
                flush=True,
            )
        case = answer_case(item["question"], result, item["reference"])
        rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "reference": item["reference"],
                "answer": case.actual_output,
                "evidence_items": len(case.retrieval_context or []),
                "agent_llm_calls": _llm_calls(exporter),
                "scores": await _score(judge, case),
            }
        )
        with capsys.disabled():
            print(
                f"[{time.monotonic() - started:5.0f}s] scored {item['id']}", flush=True
            )
    means = {
        name: statistics.mean(row["scores"][name]["score"] for row in rows)
        for name in THRESHOLDS
    }
    if "E2E_ARTIFACT_DIR" not in os.environ:
        monkeypatch.setenv("E2E_ARTIFACT_DIR", str(_REPORT_DIR))
    report = write_artifact("answer_quality", {"means": means, "questions": rows})

    assert len(report["questions"]) == 2
    below = {
        name: (mean, THRESHOLDS[name])
        for name, mean in report["means"].items()
        if mean < THRESHOLDS[name]
    }
    assert not below, f"metric means below their thresholds (mean, threshold): {below}"
