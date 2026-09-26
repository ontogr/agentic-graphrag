"""Validate verdict statuses and evidence defaults for verifier responses."""

from typing import Any

import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from agrag.agents.prompts import VERIFIER_SYSTEM
from agrag.agents.verification import VerificationResult, verify_findings


class _FakeModel:
    """Chat model stand-in that records the structured-output request."""

    def __init__(self, reply: Any = None, error: Exception | None = None) -> None:
        """Set the reply, or the error raised on invoke."""
        self.reply = reply
        self.error = error
        self.schema: Any = None
        self.messages: list[Any] = []

    def with_structured_output(self, schema: Any, **kwargs: Any) -> "_FakeModel":
        """Record the requested output type."""
        self.schema = schema
        return self

    async def ainvoke(self, messages: list[Any]) -> Any:
        """Record the messages, then return the reply or raise the error."""
        self.messages = messages
        if self.error:
            raise self.error
        return self.reply


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
    """verify_findings runs the verifier prompt on fixed inputs."""

    async def test_sends_prompt_and_inputs_and_returns_verdict(self) -> None:
        """The system message is the verifier prompt and the user message the inputs."""
        verdict = VerificationResult(reasoning="ok", status="PASS")
        model = _FakeModel(reply=verdict)

        result = await verify_findings(
            model, "Q-main?", ["sub one", "sub two"], "[E1] finding text"
        )

        assert result == verdict
        assert model.schema is VerificationResult
        system, user = model.messages
        assert isinstance(system, SystemMessage)
        assert system.content == VERIFIER_SYSTEM
        assert isinstance(user, HumanMessage)
        for part in ("Q-main?", "sub one", "sub two", "[E1] finding text"):
            assert part in user.content

    async def test_model_error_propagates(self) -> None:
        """A failing model call raises; no default verdict is invented."""
        with pytest.raises(RuntimeError, match="boom"):
            await verify_findings(_FakeModel(error=RuntimeError("boom")), "q", [], "f")

    async def test_missing_verdict_raises(self) -> None:
        """A model that returns nothing parsed is an error, not a verdict."""
        with pytest.raises(ValueError, match="no verdict"):
            await verify_findings(_FakeModel(reply=None), "q", [], "f")
