"""Tests for AgentLLMSettings and AgentSettings.

Covers ``from_openai_compatible_env`` reading ``AGENT_LLM_*`` env vars, its
fallback to the shared ``LLM_*`` vars when the agent-specific ones are unset,
direct construction, and the default/custom agent recursion limit. Sets and
tears down real environment variables with ``os.environ`` rather than
``monkeypatch``.
"""

import os

from agrag.agents.settings import AgentLLMSettings, AgentSettings
from agrag.llm.client_config import LLMClientConfig


class TestAgentLLMSettings:
    """AgentLLMSettings loads from env and from_openai_compatible_env."""

    def test_from_openai_compatible_env(self) -> None:
        """from_openai_compatible_env reads env vars."""
        os.environ["AGENT_LLM_BASE_URL"] = "http://localhost:8080"
        os.environ["AGENT_LLM_API_KEY"] = "test-key"
        os.environ["AGENT_LLM_MODEL_ID"] = "gpt-4o"
        try:
            settings = AgentLLMSettings.from_openai_compatible_env()
            assert len(settings.clients) == 1
            assert settings.clients[0].provider == "openai-generic"
            assert settings.clients[0].model == "gpt-4o"
            assert settings.clients[0].base_url == "http://localhost:8080"
        finally:
            del os.environ["AGENT_LLM_BASE_URL"]
            del os.environ["AGENT_LLM_API_KEY"]
            del os.environ["AGENT_LLM_MODEL_ID"]

    def test_falls_back_to_shared_llm_env(self) -> None:
        """Shared LLM_* vars configure the agent when AGENT_LLM_* is unset."""
        os.environ["LLM_BASE_URL"] = "http://localhost:9000/v1"
        os.environ["LLM_API_KEY"] = "shared-key"
        os.environ["LLM_MODEL_ID"] = "shared-model"
        try:
            settings = AgentLLMSettings.from_openai_compatible_env()
            assert settings.clients[0].base_url == "http://localhost:9000/v1"
            assert settings.clients[0].api_key == "shared-key"
            assert settings.clients[0].model == "shared-model"
        finally:
            del os.environ["LLM_BASE_URL"]
            del os.environ["LLM_API_KEY"]
            del os.environ["LLM_MODEL_ID"]

    def test_direct_construction(self) -> None:
        """Settings can be constructed directly."""
        settings = AgentLLMSettings(
            clients=[
                LLMClientConfig(
                    name="test",
                    provider="openai",
                    model="gpt-4o",
                    api_key="key",
                )
            ]
        )
        assert settings.strategy == "single"


class TestAgentSettings:
    """AgentSettings loads from env."""

    def test_default_recursion_limit(self) -> None:
        """Default recursion limit is 50."""
        s = AgentSettings()
        assert s.recursion_limit == 50

    def test_custom_recursion_limit(self) -> None:
        """Custom recursion limit overrides default."""
        s = AgentSettings(recursion_limit=100)
        assert s.recursion_limit == 100

    def test_max_research_attempts_default_is_three(self) -> None:
        """Default retry budget is three."""
        s = AgentSettings()
        assert s.max_research_attempts == 3

    def test_max_research_attempts_env_override(self) -> None:
        """AGENT_MAX_RESEARCH_ATTEMPTS overrides the default."""
        os.environ["AGENT_MAX_RESEARCH_ATTEMPTS"] = "5"
        try:
            s = AgentSettings()
            assert s.max_research_attempts == 5
        finally:
            del os.environ["AGENT_MAX_RESEARCH_ATTEMPTS"]
