"""Translate LLMClientConfig into the matching LangChain chat model."""

from typing import Any, Literal

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

        generic_kwargs: dict[str, Any] = {"model": config.model}
        if config.base_url:
            generic_kwargs["base_url"] = config.base_url
        if config.api_key:
            generic_kwargs["api_key"] = config.api_key
        return ChatOpenAI(**generic_kwargs)

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


def build_model_middleware(
    clients: list[LLMClientConfig],
    *,
    strategy: Literal["single", "fallback", "round_robin"] = "single",
) -> list[Any]:
    """Build agent middleware composing multiple clients per strategy.

    The agent calls ``clients[0]`` as its primary model. With more than
    one client, the returned middleware teaches the agent loop to use
    the rest: ``"fallback"`` tries the other clients in order when the
    primary model call fails, and ``"round_robin"`` rotates across
    every client per model call.

    Args:
        clients: The configured clients, in priority order.
        strategy: How to compose ``clients``. ``"single"`` ignores all
            but the first client.

    Returns:
        Middleware for create_deep_agent/create_agent; empty when there
        is nothing to compose.

    Raises:
        UnsupportedAgentProviderError: a client's provider has no
            agent-side mapping.
    """
    if strategy == "single" or len(clients) <= 1:
        return []

    models = [build_chat_model(client) for client in clients]
    if strategy == "fallback":
        from langchain.agents.middleware import (  # noqa: PLC0415
            ModelFallbackMiddleware,
        )

        return [ModelFallbackMiddleware(*models[1:])]

    from agrag.agents.middleware import (  # noqa: PLC0415
        RoundRobinModelMiddleware,
    )

    return [RoundRobinModelMiddleware(models)]
