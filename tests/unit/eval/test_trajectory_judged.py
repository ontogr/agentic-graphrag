"""Tests for the judged trajectory metrics.

The judges are scripted: a fake DeepEval judge answers task completion, and
a fake chat model answers the trajectory judge. No endpoint is called. These
tests cover how agrag builds the case and the judge input, not what the
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
    task_completion,
    trajectory_case,
    trajectory_quality,
)
from tests.unit.eval.conftest import _answer, _research_tool, _task


class _ScriptedJudge(DeepEvalBaseLLM):
    """Judge that completes every task with 0.9 and records its prompts."""

    def __init__(self) -> None:
        """Create the judge with an empty prompt log."""
        self.prompts: list[str] = []
        super().__init__("scripted")

    def load_model(self) -> Any:
        """Return no model; replies are scripted."""
        return None

    def get_model_name(self) -> str:
        """Return the fake model id."""
        return "scripted"

    def generate(self, prompt: str, schema: type[BaseModel] | None = None) -> Any:
        """Answer the outcome and verdict schemas with fixed values."""
        self.prompts.append(prompt)
        if schema is None:
            return ""
        if "outcome" in schema.model_fields:
            return schema.model_validate(
                {"task": "answer the question", "outcome": "the answer"}
            )
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


class TestTaskCompletion:
    """task_completion judges the goal from the question and the tool calls."""

    async def test_judge_sees_researcher_tools_and_task_calls(self) -> None:
        """The judge prompt holds the researcher tools, not only delegations."""
        judge = _ScriptedJudge()
        metric = task_completion(judge)

        await metric.a_measure(_case())

        assert metric.score == 0.9
        assert metric.success
        # Two judge calls per measure (outcome, then verdict), median of three.
        assert len(judge.prompts) == 6
        assert any("search_source_text" in prompt for prompt in judge.prompts)
        assert any("task" in prompt for prompt in judge.prompts)


class TestTrajectoryQuality:
    """trajectory_quality judges the steps against the question alone."""

    def test_judge_receives_question_and_steps_in_order(self) -> None:
        """The prompt holds the question, then the calls in start order."""
        chat = _ScriptedChatModel()
        metric = trajectory_quality(ChatModelJudge(chat, "scripted"))

        assert metric.measure(_case()) == 0.8
        assert len(chat.prompts) == 3
        for prompt in chat.prompts:
            assert "Who founded Zephyra Robotics?" in prompt
            assert "JSON object" in prompt
            assert prompt.index("task") < prompt.index("search_source_text")
            assert "reference_trajectory" not in prompt

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
