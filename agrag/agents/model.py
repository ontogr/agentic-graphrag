"""Translate LLMClientConfig into the matching LangChain chat model."""

from typing import Any

from agrag.llm.client_config import LLMClientConfig


class UnsupportedAgentProviderError(Exception):
    """Raised when a provider has no agent-side mapping yet."""


_UNSUPPORTED_PROVIDERS = frozenset(
    {"aws-bedrock", "vertex-ai", "openai-responses", "azure-openai"}
)


def build_chat_model(config: LLMClientConfig) -> Any:
    """Translate one LLMClientConfig into a LangChain chat model.

    Covers anthropic, openai, openai-generic (mapped to ChatOpenAI
    with base_url set), and google-ai. The remaining LLMProvider
    values are valid for BAML but have no agent-side mapping yet.

    Args:
        config: The provider, model, api_key, and base_url to use.

    Returns:
        A constructed, ready-to-call BaseChatModel.

    Raises:
        UnsupportedAgentProviderError: config.provider has no
            agent-side mapping.
    """
    if config.provider in _UNSUPPORTED_PROVIDERS:
        raise UnsupportedAgentProviderError(
            f"Provider '{config.provider}' has no agent-side mapping "
            f"yet. Supported: anthropic, openai, openai-generic, "
            f"google-ai."
        )

    if config.provider == "anthropic":
        from langchain_anthropic import (  # noqa: PLC0415
            ChatAnthropic,
        )

        return ChatAnthropic(
            model=config.model,
            api_key=config.api_key,
        )

    if config.provider == "openai":
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        kwargs: dict[str, Any] = {"model": config.model}
        if config.api_key:
            kwargs["api_key"] = config.api_key
        return ChatOpenAI(**kwargs)

    if config.provider == "openai-generic":
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        kwargs = {"model": config.model}
        if config.base_url:
            kwargs["base_url"] = config.base_url
        if config.api_key:
            kwargs["api_key"] = config.api_key
        return ChatOpenAI(**kwargs)

    if config.provider == "google-ai":
        from langchain_google_genai import (  # noqa: PLC0415
            ChatGoogleGenerativeAI,
        )

        return ChatGoogleGenerativeAI(
            model=config.model,
            google_api_key=config.api_key,
        )

    raise UnsupportedAgentProviderError(
        f"Provider '{config.provider}' has no agent-side mapping."
    )
