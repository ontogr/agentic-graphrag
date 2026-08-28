"""Tests for ExtractionLLMSettings env loading and the OpenAI env bridge."""

import pytest

from agrag.ingestion.extract import ExtractionLLMSettings
from agrag.llm.client_config import LLMClientConfig


class TestExtractionLLMSettingsEnv:
    """Settings load clients, strategy, and retry from EXTRACTION_LLM_* vars."""

    def test_loads_clients_strategy_and_retry(self, monkeypatch) -> None:
        """All three fields are read from the environment."""
        monkeypatch.setenv(
            "EXTRACTION_LLM_CLIENTS",
            '[{"name": "c", "provider": "openai", "model": "gpt-4o-mini"}]',
        )
        monkeypatch.setenv("EXTRACTION_LLM_STRATEGY", "fallback")
        monkeypatch.setenv("EXTRACTION_LLM_RETRY", '{"max_retries": 5}')
        settings = ExtractionLLMSettings()
        assert settings.strategy == "fallback"
        assert settings.retry.max_retries == 5
        assert settings.clients == [
            LLMClientConfig(name="c", provider="openai", model="gpt-4o-mini")
        ]

    def test_defaults_when_env_absent(self, monkeypatch) -> None:
        """Without env vars, strategy and retry take their defaults."""
        for var in (
            "EXTRACTION_LLM_CLIENTS",
            "EXTRACTION_LLM_STRATEGY",
            "EXTRACTION_LLM_RETRY",
        ):
            monkeypatch.delenv(var, raising=False)
        settings = ExtractionLLMSettings(clients=[])
        assert settings.strategy == "single"
        assert settings.retry.max_retries == 3


class TestFromOpenAICompatibleEnv:
    """from_openai_compatible_env reads LLM_* env vars into one generic client."""

    def test_builds_generic_client_from_env(self, monkeypatch) -> None:
        """The three LLM_* vars become one openai-generic client."""
        monkeypatch.setenv("LLM_BASE_URL", "http://localhost:4000/v1")
        monkeypatch.setenv("LLM_API_KEY", "key")
        monkeypatch.setenv("LLM_MODEL_ID", "local-model")
        monkeypatch.setattr("agrag.ingestion.extract.load_dotenv", lambda **kw: None)
        settings = ExtractionLLMSettings.from_openai_compatible_env()
        assert len(settings.clients) == 1
        client = settings.clients[0]
        assert client.provider == "openai-generic"
        assert client.model == "local-model"
        assert client.base_url == "http://localhost:4000/v1"
        assert client.api_key == "key"

    def test_raises_when_vars_absent(self, monkeypatch) -> None:
        """Missing LLM_BASE_URL/LLM_MODEL_ID is a clear error, not a silent None."""
        monkeypatch.delenv("LLM_BASE_URL", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("LLM_MODEL_ID", raising=False)
        monkeypatch.setattr("agrag.ingestion.extract.load_dotenv", lambda **kw: None)
        with pytest.raises(RuntimeError):
            ExtractionLLMSettings.from_openai_compatible_env()
