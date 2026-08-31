"""Tests for build_chat_model provider translation."""

import pytest

from agrag.agents.model import (
    UnsupportedAgentProviderError,
    build_chat_model,
)
from agrag.llm.client_config import LLMClientConfig


class TestBuildChatModel:
    """build_chat_model translates LLMClientConfig to LangChain model."""

    @pytest.mark.parametrize(
        "provider",
        ["aws-bedrock", "vertex-ai", "openai-responses", "azure-openai"],
    )
    def test_raises_for_unsupported_providers(self, provider: str) -> None:
        """Unsupported providers raise UnsupportedAgentProviderError."""
        config = LLMClientConfig(
            name="test",
            provider=provider,
            model="test-model",  # type: ignore[arg-type]
        )
        with pytest.raises(UnsupportedAgentProviderError):
            build_chat_model(config)

    def test_openai_provider_succeeds(self) -> None:
        """OpenAI provider creates a ChatOpenAI instance."""
        config = LLMClientConfig(
            name="test",
            provider="openai",
            model="gpt-4o",
            api_key="test-key",
        )
        try:
            model = build_chat_model(config)
            assert model is not None
        except ImportError:
            pytest.skip("langchain-openai not installed")

    def test_openai_generic_provider_succeeds(self) -> None:
        """OpenAI-generic provider creates a ChatOpenAI with base_url."""
        config = LLMClientConfig(
            name="test",
            provider="openai-generic",
            model="test-model",
            api_key="key",
            base_url="http://localhost:8080",
        )
        try:
            model = build_chat_model(config)
            assert model is not None
        except ImportError:
            pytest.skip("langchain-openai not installed")

    def test_anthropic_provider_succeeds(self) -> None:
        """Anthropic provider creates a ChatAnthropic instance."""
        config = LLMClientConfig(
            name="test",
            provider="anthropic",
            model="claude-3-sonnet",
            api_key="test-key",
        )
        try:
            model = build_chat_model(config)
            assert model is not None
        except ImportError:
            pytest.skip("langchain-anthropic not installed")

    def test_google_ai_provider_succeeds(self) -> None:
        """Google AI provider creates a ChatGoogleGenerativeAI instance."""
        config = LLMClientConfig(
            name="test",
            provider="google-ai",
            model="gemini-pro",
            api_key="test-key",
        )
        try:
            model = build_chat_model(config)
            assert model is not None
        except ImportError:
            pytest.skip("langchain-google-genai not installed")
