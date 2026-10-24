"""Tests for the trajectory case builder and the structural rules.

Trajectories are built by hand, so no agent or exporter is involved. These
tests cover the rules that are not plain AgentEvals matching: verifier order,
retry counting, and how the case carries the trajectory.
"""

import itertools
import json

import pytest
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase, ToolCall
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import SpanContext

from agrag.eval.trajectory import (
    Step,
    Trajectory,
    expected_tools_metric,
    read_trajectory,
    trajectory_case,
)
from tests.unit.eval.conftest import _answer, _research_tool, _step, _task


_TRACE_ID = 0x9F86D081884C7D65
_ids = itertools.count(1000)


def _case(*steps: Step) -> LLMTestCase:
    """Build a case over the given steps."""
    return trajectory_case(
        "What was founded?", "Zephyra Robotics.", Trajectory(steps=list(steps))
    )


def _calls(case: LLMTestCase) -> list[ToolCall]:
    """Return the case's tool calls, raising when they are missing."""
    if case.tools_called is None:
        raise ValueError("case needs tools_called")
    return case.tools_called


def _reason(metric: BaseMetric) -> str:
    """Return the metric's reason, raising when it is missing."""
    if metric.reason is None:
        raise ValueError("metric has no reason")
    return metric.reason


def _raw_span(output_value: str) -> ReadableSpan:
    """Build a tool span that carries one output value."""
    return ReadableSpan(
        name="search_source_text",
        context=SpanContext(_TRACE_ID, next(_ids), False),
        attributes={
            "openinference.span.kind": "TOOL",
            "tool.name": "search_source_text",
            "output.value": output_value,
        },
        start_time=10,
        end_time=20,
    )


class TestTrajectoryCase:
    """trajectory_case carries the tool calls and the trajectory."""

    def test_tools_cover_task_and_researcher_steps(self) -> None:
        """Every tool step becomes a ToolCall with its name, args and output."""
        task = _task("researcher", start=10, end=50)
        tool = _step(
            "tool",
            "search_source_text",
            start=20,
            end=30,
            args={"query": "founding"},
            output="evidence",
            subagent="researcher",
        )

        case = trajectory_case("q", "a", Trajectory(steps=[task, tool]))

        assert case.input == "q"
        assert case.actual_output == "a"
        calls = _calls(case)
        assert [(call.name, call.input_parameters) for call in calls] == [
            ("task", {"description": "delegate", "subagent_type": "researcher"}),
            ("search_source_text", {"query": "founding"}),
        ]
        assert [call.output for call in calls] == ["", "evidence"]
        metadata = case.metadata
        if metadata is None:
            raise ValueError("case needs metadata")
        assert metadata["trajectory"]["steps"][1]["name"] == "search_source_text"

    def test_model_steps_are_not_tool_calls(self) -> None:
        """LLM steps stay out of tools_called."""
        case = _case(_task("researcher", 10, 50), _answer(60, 70))

        assert [call.name for call in _calls(case)] == ["task"]

    def test_metric_without_a_trajectory_raises(self) -> None:
        """A case from elsewhere is an error, not a silent pass."""
        case = LLMTestCase(input="q", actual_output="a")

        with pytest.raises(ValueError, match="trajectory_case"):
            expected_tools_metric(["task"]).measure(case)


class TestExpectedTools:
    """Expected tools must appear; extra tools and arguments do not matter."""

    def test_all_names_present_pass(self) -> None:
        """Every expected name called passes."""
        metric = expected_tools_metric(["task", "search_source_text"])

        score = metric.measure(
            _case(
                _task("researcher", 10, 50),
                _research_tool("search_source_text", 20, 30),
                _answer(60, 70),
            )
        )

        assert score == 1.0
        assert metric.success

    def test_one_missing_name_fails_and_names_it(self) -> None:
        """A missing name fails and the reason names it."""
        metric = expected_tools_metric(["task", "look_up_entity"])

        score = metric.measure(
            _case(
                _task("researcher", 10, 50),
                _research_tool("search_source_text", 20, 30),
                _answer(60, 70),
            )
        )

        assert score == 0.0
        assert "look_up_entity" in _reason(metric)

    def test_extra_tools_do_not_matter(self) -> None:
        """Calls beyond the expected names still pass."""
        metric = expected_tools_metric(["task"])

        score = metric.measure(
            _case(
                _task("researcher", 10, 50),
                _research_tool("search_source_text", 20, 30),
                _research_tool("look_up_entity", 35, 40),
                _answer(60, 70),
            )
        )

        assert score == 1.0

    def test_tool_arguments_are_ignored(self) -> None:
        """The same names with different arguments still pass."""
        metric = expected_tools_metric(["task"])

        score = metric.measure(_case(_task("verifier", 10, 50), _answer(60, 70)))

        assert score == 1.0

    def test_any_of_group_passes_when_one_member_called(self) -> None:
        """A nested alternative group is satisfied by any one of its names."""
        metric = expected_tools_metric([["task", "look_up_entity"]])

        score = metric.measure(
            _case(_research_tool("look_up_entity", 20, 30), _answer(60, 70))
        )

        assert score == 1.0

    def test_any_of_group_fails_when_no_member_called(self) -> None:
        """A nested alternative group with no called member fails and names it."""
        metric = expected_tools_metric([["task", "look_up_entity"]])

        score = metric.measure(
            _case(_research_tool("search_source_text", 20, 30), _answer(60, 70))
        )

        assert score == 0.0
        assert "look_up_entity" in _reason(metric)

    def test_required_name_and_any_of_group_together(self) -> None:
        """A mix of required names and alternative groups needs both."""
        metric = expected_tools_metric([["task", "look_up_entity"], "answer_question"])

        score = metric.measure(
            _case(_research_tool("look_up_entity", 20, 30), _answer(60, 70))
        )

        assert score == 0.0
        assert "answer_question" in _reason(metric)

    def test_no_tool_steps_fail_and_list_what_was_called(self) -> None:
        """A trajectory without the required name fails and shows the calls."""
        metric = expected_tools_metric(["task"])

        score = metric.measure(
            _case(_research_tool("search_source_text", 20, 30), _answer(60, 70))
        )

        assert score == 0.0
        assert "task" in _reason(metric)
        assert "search_source_text" in _reason(metric)


class TestOutputUnwrapping:
    """A step's output is the tool message content, or the raw text."""

    def test_serialized_tool_message_becomes_its_content(self) -> None:
        """The data.content of a serialized ToolMessage is the output."""
        span = _raw_span(
            json.dumps(
                {
                    "type": "tool",
                    "data": {"content": "found it", "tool_call_id": "1"},
                }
            )
        )

        assert read_trajectory([span]).steps[0].output == "found it"

    def test_plain_string_is_kept(self) -> None:
        """An output that is not a ToolMessage stays as is."""
        span = _raw_span("raw text")

        assert read_trajectory([span]).steps[0].output == "raw text"
