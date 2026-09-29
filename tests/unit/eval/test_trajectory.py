"""Tests for the trajectory reader and span capture.

Spans are hand-built with fixed start and end times, so no model or exporter
is involved except in the ``SpanCapture`` tests. These tests cover how agrag
reads kind, order, parents and arguments from spans, not what OpenInference
writes into them.
"""

import itertools
import json

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import SpanContext, get_tracer_provider

from agrag.eval.trajectory import (
    SpanCapture,
    read_trajectory,
    trajectory_case,
    verifier_before_answer_metric,
)


_TRACE_ID = 0x9F86D081884C7D65
_ids = itertools.count(1)


def _span(
    name: str,
    kind: str | None = None,
    *,
    tool: str | None = None,
    input_value: str | None = None,
    output_value: str | None = None,
    parent: ReadableSpan | None = None,
    start: int = 0,
    end: int = 0,
) -> ReadableSpan:
    """Build one finished span with fixed times."""
    attributes: dict[str, str] = {}
    if kind is not None:
        attributes["openinference.span.kind"] = kind
    if tool is not None:
        attributes["tool.name"] = tool
    if input_value is not None:
        attributes["input.value"] = input_value
    if output_value is not None:
        attributes["output.value"] = output_value
    return ReadableSpan(
        name=name,
        context=SpanContext(_TRACE_ID, next(_ids), False),
        parent=parent.context if parent is not None else None,
        attributes=attributes,
        start_time=start,
        end_time=end,
    )


def _task(subagent_type: str, start: int, end: int) -> ReadableSpan:
    """Build a delegation span for one subagent type."""
    return _span(
        "task",
        "TOOL",
        tool="task",
        input_value=json.dumps(
            {"description": "delegate", "subagent_type": subagent_type}
        ),
        start=start,
        end=end,
    )


class TestReadTrajectory:
    """read_trajectory keeps tool and model steps in start order."""

    def test_researcher_tool_span_names_its_subagent(self) -> None:
        """A tool span under a task span reads the task's subagent type."""
        task = _task("researcher", start=10, end=50)
        tool = _span(
            "search_source_text",
            "TOOL",
            tool="search_source_text",
            input_value=json.dumps({"query": "founding"}),
            parent=task,
            start=20,
            end=30,
        )
        planner = _span("ChatOpenAI", "LLM", start=60, end=70)

        steps = read_trajectory([tool, planner, task]).steps

        assert [step.name for step in steps] == [
            "task",
            "search_source_text",
            "ChatOpenAI",
        ]
        assert steps[0].subagent is None
        assert steps[1].subagent == "researcher"
        assert steps[1].kind == "tool"
        assert steps[1].args == {"query": "founding"}
        assert steps[2].subagent is None
        assert steps[2].kind == "llm"

    def test_chain_spans_are_dropped(self) -> None:
        """Graph node spans never become steps."""
        chain = _span("LangGraph", "CHAIN", start=5, end=60)
        tool = _span("task", "TOOL", tool="task", start=10, end=20)

        steps = read_trajectory([chain, tool]).steps

        assert [step.name for step in steps] == ["task"]

    def test_steps_follow_start_time_not_export_order(self) -> None:
        """A late-exported span still sorts by when it started."""
        first = _span("look_up_entity", "TOOL", tool="look_up_entity", start=10, end=40)
        second = _span("ChatOpenAI", "LLM", start=20, end=30)

        steps = read_trajectory([second, first]).steps

        assert [step.name for step in steps] == ["look_up_entity", "ChatOpenAI"]

    def test_parallel_task_spans_own_their_child_tool_steps(self) -> None:
        """Each child tool reads the subagent type of its own task span."""
        first_task = _task("researcher", start=10, end=50)
        second_task = _task("verifier", start=15, end=45)
        first_tool = _span(
            "search_source_text",
            "TOOL",
            tool="search_source_text",
            parent=first_task,
            start=20,
            end=30,
        )
        verifier_llm = _span("ChatOpenAI", "LLM", parent=second_task, start=25, end=35)

        steps = read_trajectory(
            [first_task, second_task, first_tool, verifier_llm]
        ).steps

        by_name = {step.name: step for step in steps}
        assert by_name["search_source_text"].subagent == "researcher"
        assert by_name["ChatOpenAI"].subagent == "verifier"

    def test_non_json_input_does_not_raise(self) -> None:
        """An input that is not JSON is kept as raw text."""
        tool = _span(
            "search_source_text",
            "TOOL",
            tool="search_source_text",
            input_value="not json{{",
            start=10,
            end=20,
        )

        steps = read_trajectory([tool]).steps

        assert steps[0].args == {"input": "not json{{"}

    def test_missing_input_gives_empty_args(self) -> None:
        """A span without input.value reads no arguments."""
        tool = _span("task", "TOOL", tool="task", start=10, end=20)

        assert read_trajectory([tool]).steps[0].args == {}

    def test_step_carries_span_id_and_parent_chain(self) -> None:
        """A nested step records its span and every ancestor."""
        task = _task("researcher", start=10, end=50)
        chain = _span("tools", "CHAIN", parent=task, start=15, end=45)
        tool = _span(
            "search_source_text",
            "TOOL",
            tool="search_source_text",
            parent=chain,
            start=20,
            end=30,
        )

        (step,) = read_trajectory([task, chain, tool]).steps[1:2]

        assert step.span_id == f"{tool.context.span_id:016x}"
        assert step.parent_ids[0] == f"{chain.context.span_id:016x}"
        assert step.parent_ids[1] == f"{task.context.span_id:016x}"
        assert step.subagent == "researcher"


class TestSpanCapture:
    """SpanCapture isolates one run's spans from the global provider."""

    def test_leaves_the_global_provider_unchanged(self) -> None:
        """Capturing never installs a global provider."""
        before = get_tracer_provider()

        with (
            SpanCapture() as capture,
            capture.tracer.start_as_current_span(
                "search_source_text",
                attributes={
                    "openinference.span.kind": "TOOL",
                    "tool.name": "search_source_text",
                },
            ),
        ):
            pass

        assert get_tracer_provider() is before
        assert [step.name for step in capture.trajectory().steps] == [
            "search_source_text"
        ]

    def test_two_captures_do_not_share_spans(self) -> None:
        """Each capture reads only the spans its own tracer received."""
        with (
            SpanCapture() as first,
            first.tracer.start_as_current_span(
                "first_tool",
                attributes={"openinference.span.kind": "TOOL"},
            ),
        ):
            pass
        with SpanCapture():
            pass

        assert [step.name for step in first.trajectory().steps] == ["first_tool"]


class TestNonAgentSpansAreExcluded:
    """Spans agrag opens, and judge calls, never read as planner steps."""

    def test_agrag_spans_are_never_steps(self) -> None:
        """A BAML request span is not a model step, whatever its kind says."""
        request = _span(
            "agrag.llm.request",
            "LLM",
            input_value='{"messages": []}',
            start=10,
            end=20,
        )

        assert read_trajectory([request]).steps == []

    def test_an_llm_span_under_a_judge_is_not_a_step(self) -> None:
        """A judge call sharing the capture never reads as the planner."""
        judge = _span("agrag.eval.judge", start=80, end=100)
        judge_llm = _span(
            "ChatOpenAI",
            "LLM",
            input_value='{"messages": []}',
            parent=judge,
            start=85,
            end=95,
        )

        assert read_trajectory([judge, judge_llm]).steps == []

    def test_a_judge_llm_span_does_not_outdate_the_answer(self) -> None:
        """A late judge call does not make a correct trajectory look wrong."""
        verifier = _task("verifier", start=10, end=20)
        answer = _span("ChatOpenAI", "LLM", start=60, end=70)
        judge = _span("agrag.eval.judge", start=80, end=100)
        judge_llm = _span("ChatOpenAI", "LLM", parent=judge, start=85, end=95)

        trajectory = read_trajectory([verifier, answer, judge, judge_llm])

        assert [step.name for step in trajectory.steps] == ["task", "ChatOpenAI"]
        case = trajectory_case("q", "a", trajectory)
        score = verifier_before_answer_metric().measure(case)
        assert score == 1.0

    def test_a_baml_request_span_does_not_outdate_the_answer(self) -> None:
        """A late BAML call does not make a correct trajectory look wrong."""
        verifier = _task("verifier", start=10, end=20)
        answer = _span("ChatOpenAI", "LLM", start=60, end=70)
        request = _span("agrag.llm.request", "LLM", input_value="{}", start=85, end=95)

        trajectory = read_trajectory([verifier, answer, request])

        case = trajectory_case("q", "a", trajectory)
        score = verifier_before_answer_metric().measure(case)
        assert score == 1.0

    def test_a_late_planner_answer_still_fails(self) -> None:
        """The exclusion does not weaken the rule it protects."""
        verifier = _task("verifier", start=65, end=80)
        answer = _span("ChatOpenAI", "LLM", start=60, end=70)

        trajectory = read_trajectory([verifier, answer])
        case = trajectory_case("q", "a", trajectory)

        assert verifier_before_answer_metric().measure(case) == 0.0

    def test_a_judge_llm_span_cannot_rescue_a_late_verifier(self) -> None:
        """A judge call that starts last must not flip the score to 1.0.

        The judge ``LLM`` span is the latest ``LLM`` step in the raw span list.
        Admitting it would make the verifier look early; excluding it leaves
        the planner's own answer as the last step, so the verifier really did
        finish after the answer started and the score is 0.0.
        """
        verifier = _task("verifier", start=65, end=80)
        answer = _span("ChatOpenAI", "LLM", start=60, end=70)
        judge = _span("agrag.eval.judge", start=80, end=100)
        judge_llm = _span("ChatOpenAI", "LLM", parent=judge, start=85, end=95)

        trajectory = read_trajectory([verifier, answer, judge, judge_llm])
        case = trajectory_case("q", "a", trajectory)

        assert verifier_before_answer_metric().measure(case) == 0.0

    def test_a_baml_request_span_cannot_rescue_a_late_verifier(self) -> None:
        """A late BAML request must not flip the score to 1.0 either.

        The request span carries the LLM kind and starts after the verifier
        ended, so counting it as a planner step would hide the real ordering.
        """
        verifier = _task("verifier", start=65, end=80)
        answer = _span("ChatOpenAI", "LLM", start=60, end=70)
        request = _span("agrag.llm.request", "LLM", input_value="{}", start=85, end=95)

        trajectory = read_trajectory([verifier, answer, request])
        case = trajectory_case("q", "a", trajectory)

        assert verifier_before_answer_metric().measure(case) == 0.0
