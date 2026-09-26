"""Verifier calibration regression test on a FinQA-derived verdict set.

Runs the real verifier on the 60 fixed (question, findings) items of
``tests/fixtures/eval/verifier`` (FinQA, MIT licence, see the ``NOTICE`` there),
20 for each verdict, and gates on the macro F1 over the three verdicts. The
report goes to ``reports/eval/verifier_calibration.json``, or to the directory in
``E2E_ARTIFACT_DIR``. It has per-class scores, the confusion matrix, the error
count and the scores over the items that a person reviewed. The test skips
without ``LLM_*`` settings.

The threshold is the lowest of three baseline runs minus 0.05, rounded down to
0.05. Baseline runs (macro F1):

    run 1: 0.967 (0 errors)
    run 2: 0.983 (0 errors)
    run 3: 0.950 (0 errors)

The verifier runs as an agent with the verdict tool forced, so a run gave no
missing verdicts. The misses are wrong verdicts, mostly a ``CONTRADICTORY`` item
read as ``PASS`` or ``INSUFFICIENT``. An always-PASS verifier scores 0.33.
"""

import os
from pathlib import Path

import pytest

from agrag.agents.model import build_chat_model
from agrag.agents.settings import AgentLLMSettings
from agrag.eval import VerdictItem, run_verifier, verdict_report
from tests.integration.e2e._artifact import write_artifact


FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "eval" / "verifier"
REPORT_DIR = Path(__file__).parents[3] / "reports" / "eval"
# Endpoints often limit concurrent requests, and a 429 becomes an ERROR verdict.
CONCURRENCY = 2
# A call that fails on 429 retries this many times before it counts as an error.
MAX_RETRIES = 8

# Minimum macro F1 over PASS, INSUFFICIENT and CONTRADICTORY.
THRESHOLD = 0.90


def _verifier_model() -> object:
    """Build the agent's own chat model, or skip when no endpoint is configured."""
    try:
        settings = AgentLLMSettings.from_openai_compatible_env()
    except RuntimeError:
        pytest.skip("LLM endpoint not configured")
    if not settings.clients[0].api_key:
        pytest.skip("LLM API key not configured")
    return build_chat_model(settings.clients[0]).model_copy(
        update={"max_retries": MAX_RETRIES}
    )


async def test_verifier_macro_f1_meets_threshold_on_finqa_verdicts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The verifier gives the gold verdict often enough to pass the gate."""
    model = _verifier_model()
    lines = (FIXTURE_DIR / "verdict_items.jsonl").read_text().splitlines()
    items = [VerdictItem.model_validate_json(line) for line in lines]
    predicted = await run_verifier(model, items, concurrency=CONCURRENCY)

    gold = [item.gold for item in items]
    report = verdict_report(gold, predicted)
    reviewed = [
        (item.gold, label)
        for item, label in zip(items, predicted, strict=True)
        if item.human_reviewed
    ]
    reviewed_report = (
        verdict_report(*map(list, zip(*reviewed, strict=True))) if reviewed else None
    )

    if "E2E_ARTIFACT_DIR" not in os.environ:
        monkeypatch.setenv("E2E_ARTIFACT_DIR", str(REPORT_DIR))
    written = write_artifact(
        "verifier_calibration",
        {
            "items": len(items),
            "report": report.model_dump(),
            "reviewed_items": len(reviewed),
            "reviewed_report": (
                None if reviewed_report is None else reviewed_report.model_dump()
            ),
        },
    )

    assert written["items"] == len(items)
    assert report.macro_f1 >= THRESHOLD
