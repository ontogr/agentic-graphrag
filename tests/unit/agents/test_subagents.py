"""Validate the researcher and verifier subagent specifications and wiring."""

from typing import Any

from agrag.agents.prompts import RESEARCHER_SYSTEM, VERIFIER_SYSTEM
from agrag.agents.subagents import make_researcher_spec, make_verifier_spec
from agrag.agents.verification import VerificationResult
from agrag.common.data_models.graph_schema import GENERIC


class TestMakeResearcherSpec:
    """make_researcher_spec returns the SubAgent-shaped dict."""

    def test_shape(self) -> None:
        """Every expected key is present with the right values."""
        tools: list[Any] = [object()]
        middleware: list[Any] = [object()]
        spec = make_researcher_spec(tools, middleware, GENERIC)

        assert spec["name"] == "researcher"
        assert spec["description"] == "Researches a sub-question using graph tools."
        assert spec["tools"] is tools
        assert spec["middleware"] is middleware
        assert spec["system_prompt"] != ""

    def test_system_prompt_carries_schema_summary(self) -> None:
        """The schema summary is substituted, placeholder removed."""
        spec = make_researcher_spec([], [], GENERIC)

        assert "{schema_summary}" not in spec["system_prompt"]
        assert GENERIC.to_compact_summary() in spec["system_prompt"]

    def test_system_prompt_is_researcher_system_with_summary(self) -> None:
        """The prompt is RESEARCHER_SYSTEM with the placeholder filled."""
        spec = make_researcher_spec([], [], GENERIC)

        expected = RESEARCHER_SYSTEM.replace(
            "{schema_summary}", GENERIC.to_compact_summary()
        )
        assert spec["system_prompt"] == expected


class TestMakeVerifierSpec:
    """make_verifier_spec returns the SubAgent-shaped dict."""

    def test_shape(self) -> None:
        """Every expected key is present with the right values."""
        middleware: list[Any] = [object()]
        spec = make_verifier_spec(middleware)

        assert spec["name"] == "verifier"
        assert spec["tools"] == []
        assert "tools" in spec
        assert spec["middleware"] is middleware
        assert spec["system_prompt"] == VERIFIER_SYSTEM
        assert spec["mode"] == "isolated"

    def test_response_format_is_verification_result(self) -> None:
        """The structured verdict type reaches response_format."""
        spec = make_verifier_spec([])

        assert spec["response_format"] is VerificationResult
