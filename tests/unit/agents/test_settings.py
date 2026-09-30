"""Tests for AgentLLMSettings.

Covers ``from_openai_compatible_env`` reading ``AGENT_LLM_*`` env vars and its
fallback to the shared ``LLM_*`` vars when the agent-specific ones are unset.
Sets and tears down real environment variables with ``os.environ`` rather than
``monkeypatch``. Also covers validation errors leaving out values read from
``.env``.
"""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from agrag.agents.settings import AgentLLMSettings


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

    def test_missing_clients_error_omits_env_file_secrets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing-field error leaves out the secrets that .env holds."""
        (tmp_path / ".env").write_text("NEO4J_PASSWORD=pw-3e7a\n")
        monkeypatch.chdir(tmp_path)

        with pytest.raises(ValidationError) as exc_info:
            AgentLLMSettings()

        assert "pw-3e7a" not in str(exc_info.value)
