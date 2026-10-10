"""Tests for the judged trajectory metrics.

The judges are scripted: a fake chat model answers the trajectory judge, and a
fake DeepEval judge fills the slot that requires one. No endpoint is called.
These tests cover how agrag builds the case and the judge input, not what the
libraries score.
"""

from typing import Any

import pytest
from deepeval.models import DeepEvalBaseLLM
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field

from agrag.eval.judge import ChatModelJudge
from agrag.eval.trajectory import (
    Trajectory,
    trajectory_case,
    trajectory_quality,
)
from tests.unit.eval.conftest import _answer, _research_tool, _task


class _ScriptedJudge(DeepEvalBaseLLM):
    """Judge that answers every schema with a fixed verdict."""

    def __init__(self) -> None:
        """Create the judge."""
        super().__init__("scripted")

    def load_model(self) -> Any:
        """Return no model; replies are scripted."""
        return None

    def get_model_name(self) -> str:
        """Return the fake model id."""
        return "scripted"

    def generate(self, prompt: str, schema: type[BaseModel] | None = None) -> Any:
        """Answer a schema with a fixed verdict."""
        if schema is None:
            return ""
        return schema.model_validate({"verdict": 0.9, "reason": "scripted"})

    async def a_generate(
        self, prompt: str, schema: type[BaseModel] | None = None
    ) -> Any:
        """Answer asynchronously. See ``generate``."""
        return self.generate(prompt, schema)


class _ScriptedChatModel(BaseChatModel):
    """Chat model that scores every trajectory and records its prompts."""

    prompts: list[str] = Field(default_factory=list)
    score: float = 0.8
    fail_on: str | None = None
    raw: Any = None

    @property
    def _llm_type(self) -> str:
        """Name the fake model type."""
        return "scripted"

    def _generate(
        self,
        messages: list[Any],
        stop: Any = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Never called; structured replies go through the stub below."""
        raise AssertionError("use with_structured_output")

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        """Return a stub that scores the prompt with a fixed value."""
        model = self

        class _StructuredReply:
            def invoke(self, messages: Any, *args: Any, **kwargs: Any) -> Any:
                first = messages[0]
                content = first["content"] if isinstance(first, dict) else str(first)
                model.prompts.append(
                    content if isinstance(content, str) else str(content)
                )
                if model.fail_on is not None and model.fail_on in model.prompts[-1]:
                    raise RuntimeError("judge failed")
                if model.raw is not None:
                    return model.raw
                return {"score": model.score, "reasoning": "scripted"}

        return _StructuredReply()


def _trajectory() -> Trajectory:
    """Build a run with a delegation, a researcher tool and an answer."""
    return Trajectory(
        steps=[
            _task("researcher", start=10, end=50),
            _research_tool("search_source_text", start=20, end=30),
            _task("verifier", start=40, end=55),
            _answer(start=60, end=70),
        ]
    )


def _case() -> Any:
    """Build a case over the shared trajectory."""
    return trajectory_case(
        "Who founded Zephyra Robotics?", "Marlow Quist founded it.", _trajectory()
    )


class TestTrajectoryQuality:
    """trajectory_quality judges the steps against the question alone."""

    def test_judge_receives_question_and_steps_in_order(self) -> None:
        """The prompt holds the question, then the calls in start order."""
        chat = _ScriptedChatModel()
        metric = trajectory_quality(ChatModelJudge(chat, "scripted"))

        assert metric.measure(_case()) == 0.8
        assert len(chat.prompts) == 1
        for prompt in chat.prompts:
            assert "Who founded Zephyra Robotics?" in prompt
            assert "JSON object" in prompt
            assert prompt.index("task") < prompt.index("search_source_text")
            assert "reference_trajectory" not in prompt

    def test_judge_receives_tool_outputs(self) -> None:
        """The prompt holds each tool's output, not only its call."""
        trajectory = Trajectory(
            steps=[
                _task("researcher", start=10, end=50),
                _research_tool(
                    "search_source_text", start=20, end=30, output="no new results"
                ),
            ]
        )
        case = trajectory_case("Who founded Zephyra Robotics?", "unknown", trajectory)
        chat = _ScriptedChatModel()
        metric = trajectory_quality(ChatModelJudge(chat, "scripted"))

        metric.measure(case)

        assert "no new results" in chat.prompts[0]

    def test_judge_receives_calls_and_results_interleaved(self) -> None:
        """Each call is followed by its own result, not batched with others."""
        trajectory = Trajectory(
            steps=[
                _research_tool("search_a", start=10, end=20, output="result-a"),
                _research_tool("search_b", start=30, end=40, output="result-b"),
            ]
        )
        case = trajectory_case("Who founded Zephyra Robotics?", "unknown", trajectory)
        chat = _ScriptedChatModel()
        metric = trajectory_quality(ChatModelJudge(chat, "scripted"))

        metric.measure(case)

        prompt = chat.prompts[0]
        assert (
            prompt.index("search_a")
            < prompt.index("result-a")
            < prompt.index("search_b")
        )

    def test_bare_number_reply_scores(self) -> None:
        """A judge that answers with a bare number still scores."""
        chat = _ScriptedChatModel(score=0.7, raw=0.7)
        metric = trajectory_quality(ChatModelJudge(chat, "scripted"))

        assert metric.measure(_case()) == 0.7

    def test_bare_numeric_string_reply_scores(self) -> None:
        """A judge that answers with a numeric string still scores."""
        chat = _ScriptedChatModel(raw="0.7")
        metric = trajectory_quality(ChatModelJudge(chat, "scripted"))

        assert metric.measure(_case()) == 0.7

    def test_out_of_range_bare_number_does_not_score(self) -> None:
        """A bare number outside 0 to 1 does not silently pass as a score."""
        chat = _ScriptedChatModel(raw=2)
        metric = trajectory_quality(ChatModelJudge(chat, "scripted"))

        with pytest.raises(TypeError):
            metric.measure(_case())

    def test_judge_error_surfaces(self) -> None:
        """A judge error is not scored as a pass."""
        chat = _ScriptedChatModel(fail_on="task")
        metric = trajectory_quality(ChatModelJudge(chat, "scripted"))

        with pytest.raises(RuntimeError, match="judge failed"):
            metric.measure(_case())

    def test_judge_without_chat_model_raises(self) -> None:
        """A judge holding no chat model cannot grade a trajectory."""
        with pytest.raises(TypeError, match="chat model"):
            trajectory_quality(_ScriptedJudge())
