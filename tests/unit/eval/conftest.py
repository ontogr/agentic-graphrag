"""Shared fixtures for the agrag.eval unit tests."""

import itertools
from typing import Literal

import pytest

from agrag.eval.trajectory import Step


_ids = itertools.count(1000)


@pytest.fixture(autouse=True)
def _deepeval_telemetry_opt_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep DeepEval from sending telemetry during unit tests."""
    monkeypatch.setenv("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")


def _step(
    kind: Literal["tool", "llm"],
    name: str,
    *,
    start: int,
    end: int,
    args: dict | None = None,
    output: str = "",
    subagent: str | None = None,
) -> Step:
    """Build one trajectory step with fixed times."""
    return Step(
        kind=kind,
        name=name,
        args=args or {},
        output=output,
        span_id=f"{next(_ids):016x}",
        parent_ids=[],
        started=start,
        ended=end,
        subagent=subagent,
    )


def _task(subagent_type: str, start: int, end: int) -> Step:
    """Build a delegation step for one subagent type."""
    return _step(
        "tool",
        "task",
        start=start,
        end=end,
        args={"description": "delegate", "subagent_type": subagent_type},
    )


def _research_tool(name: str, start: int, end: int) -> Step:
    """Build a researcher tool step."""
    return _step("tool", name, start=start, end=end, subagent="researcher")


def _answer(start: int, end: int) -> Step:
    """Build the planner model step that wrote the answer."""
    return _step("llm", "ChatOpenAI", start=start, end=end, subagent=None)
