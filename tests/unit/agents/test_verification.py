"""Validate verdict statuses and evidence defaults for verifier responses."""

from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import ValidationError

from agrag.agents.prompts import VERIFIER_SYSTEM
from agrag.agents.verification import VerificationResult, verify_findings


class _ScriptedModel(BaseChatModel):
    """Chat model that answers with a fixed reply and records what it is sent."""

    reply: AIMessage | None = None
    error: Exception | None = None
    seen: list[Any] = []
    bound_tools: list[Any] = []

    @property
    def _llm_type(self) -> str:
        """Name the fake model type."""
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "_ScriptedModel":
        """Record the tools the agent binds, and the tool choice."""
        self.bound_tools = [tools, kwargs]
        return self

    def _generate(
        self,
        messages: list[Any],
        stop: Any = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Record the messages, then return the reply or raise the error."""
        self.seen = messages
        if self.error:
            raise self.error
        return ChatResult(generations=[ChatGeneration(message=self.reply)])


def _verdict_call(status: str = "PASS") -> AIMessage:
    """Build a model reply that calls the verdict tool."""
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "VerificationResult",
                "args": {"reasoning": "ok", "status": status},
                "id": "call-1",
            }
        ],
    )


class TestVerificationResult:
    """VerificationResult validates its status literal."""

    @pytest.mark.parametrize("status", ["PASS", "INSUFFICIENT", "CONTRADICTORY"])
    def test_valid_status_values_accepted(self, status: str) -> None:
        """Each documented verdict constructs."""
        result = VerificationResult(
            reasoning="checked every sub-question", status=status
        )
        assert result.status == status

    def test_invalid_status_rejected(self) -> None:
        """A value outside the three literals is a validation error."""
        data: dict[str, Any] = {
            "reasoning": "checked",
            "status": "MAYBE",
        }
        with pytest.raises(ValidationError):
            VerificationResult(**data)


class TestVerifyFindings:
    """verify_findings runs the verifier agent on fixed inputs."""

    async def test_sends_prompt_and_inputs_and_returns_verdict(self) -> None:
        """The system message is the verifier prompt and the user message the inputs."""
        model = _ScriptedModel(reply=_verdict_call("INSUFFICIENT"))

        result = await verify_findings(
            model, "Q-main?", ["sub one", "sub two"], "[E1] finding text"
        )

        assert result == VerificationResult(reasoning="ok", status="INSUFFICIENT")
        system, user = model.seen
        assert isinstance(system, SystemMessage)
        assert system.content == VERIFIER_SYSTEM
        assert isinstance(user, HumanMessage)
        for part in ("Q-main?", "1. sub one", "2. sub two", "[E1] finding text"):
            assert part in user.content

    async def test_model_must_answer_through_the_verdict_tool(self) -> None:
        """Only the verdict tool is bound, and the model must call a tool."""
        model = _ScriptedModel(reply=_verdict_call())

        await verify_findings(model, "q", [], "f")

        tools, options = model.bound_tools
        assert [tool.name for tool in tools] == ["VerificationResult"]
        assert options["tool_choice"] == "any"

    async def test_model_error_propagates(self) -> None:
        """A failing model call raises; no default verdict is invented."""
        with pytest.raises(RuntimeError, match="boom"):
            await verify_findings(
                _ScriptedModel(error=RuntimeError("boom")), "q", [], "f"
            )

    async def test_missing_verdict_raises(self) -> None:
        """A model that never calls the verdict tool is an error, not a verdict."""
        model = _ScriptedModel(reply=AIMessage(content="looks fine to me"))

        with pytest.raises(ValueError, match="no verdict"):
            await verify_findings(model, "q", [], "f")
