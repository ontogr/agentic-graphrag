"""Tests for ExtractionLLMSettings env loading and the OpenAI env bridge.

Covers reading ``EXTRACTION_LLM_CLIENTS``/``_STRATEGY``/``_RETRY`` and their
defaults, and ``from_openai_compatible_env`` building a single
openai-generic client from ``LLM_BASE_URL``, ``LLM_API_KEY``, and
``LLM_MODEL_ID``. Uses ``monkeypatch.setenv``/``delenv`` for environment
variables. The ``from_openai_compatible_env`` tests patch its explicit
``load_dotenv()`` call to a no-op; the ``ExtractionLLMSettings()`` tests
rely on pydantic-settings' own ``env_file`` loading and are not protected
by that patch.
"""

import pytest

from agrag.ingestion.extract import ExtractionLLMSettings


class TestExtractionLLMSettingsEnv:
    """Settings load clients, strategy, and retry from EXTRACTION_LLM_* vars."""


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
