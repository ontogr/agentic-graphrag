"""Tests for ``ExtractionLLMSettings.from_openai_compatible_env``.

Covers building a single openai-generic client from ``LLM_BASE_URL``,
``LLM_API_KEY``, and ``LLM_MODEL_ID``, and raising when they are absent.
Uses ``monkeypatch.setenv``/``delenv`` for environment variables, and
patches the explicit ``load_dotenv()`` call to a no-op.
"""

import pytest

from agrag.ingestion.extract import ExtractionLLMSettings


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
        assert client.api_key is not None
        assert client.api_key.get_secret_value() == "key"

    def test_raises_when_vars_absent(self, monkeypatch) -> None:
        """Missing LLM_BASE_URL/LLM_MODEL_ID is a clear error, not a silent None."""
        monkeypatch.delenv("LLM_BASE_URL", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("LLM_MODEL_ID", raising=False)
        monkeypatch.setattr("agrag.ingestion.extract.load_dotenv", lambda **kw: None)
        with pytest.raises(RuntimeError):
            ExtractionLLMSettings.from_openai_compatible_env()

    def test_reads_dotenv_from_the_working_directory(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """The working directory .env supplies the shared LLM model."""
        for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL_ID"):
            monkeypatch.setenv(name, "placeholder")
            monkeypatch.delenv(name)
        (tmp_path / ".env").write_text(
            "LLM_BASE_URL=http://localhost:4000/v1\nLLM_MODEL_ID=from-dotenv\n"
        )
        monkeypatch.chdir(tmp_path)

        settings = ExtractionLLMSettings.from_openai_compatible_env()

        assert settings.clients[0].model == "from-dotenv"
