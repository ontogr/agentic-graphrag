"""Tests for build_chat_model and build_model_middleware in agrag.agents.model.

Covers unsupported providers (aws-bedrock, vertex-ai, openai-responses,
azure-openai) raising UnsupportedAgentProviderError, parametrized over
provider names. Also covers build_model_middleware's strategy handling:
"single" and a single client never produce middleware, "fallback" composes
the clients after the first, and "round_robin" wraps all clients in
RoundRobinModelMiddleware.
"""

import pytest

from agrag.agents.model import (
    UnsupportedAgentProviderError,
    build_chat_model,
    build_model_middleware,
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


class TestBuildModelMiddleware:
    """build_model_middleware composes extra clients per strategy."""

    @staticmethod
    def _clients(count: int) -> list[LLMClientConfig]:
        """Build count OpenAI client configs."""
        return [
            LLMClientConfig(
                name=f"client-{i}",
                provider="openai",
                model=f"model-{i}",
                api_key="test-key",
            )
            for i in range(count)
        ]

    def test_single_strategy_returns_no_middleware(self) -> None:
        """Strategy single never composes middleware, even with clients."""
        assert build_model_middleware(self._clients(2), strategy="single") == []

    def test_one_client_returns_no_middleware(self) -> None:
        """One client never composes middleware, even for multi strategies."""
        assert build_model_middleware(self._clients(1), strategy="fallback") == []
        assert build_model_middleware(self._clients(1), strategy="round_robin") == []

    def test_fallback_composes_remaining_clients(self) -> None:
        """Strategy fallback returns middleware over clients after the first."""
        clients = self._clients(3)
        try:
            middleware = build_model_middleware(clients, strategy="fallback")
        except ImportError:
            pytest.skip("langchain not installed")

        assert len(middleware) == 1
        assert [model.model_name for model in middleware[0].models] == [
            "model-1",
            "model-2",
        ]

    def test_round_robin_composes_all_clients(self) -> None:
        """Strategy round_robin returns middleware rotating over all clients."""
        from agrag.agents.middleware import (  # noqa: PLC0415
            RoundRobinModelMiddleware,
        )

        clients = self._clients(2)
        try:
            middleware = build_model_middleware(clients, strategy="round_robin")
        except ImportError:
            pytest.skip("langchain not installed")

        assert len(middleware) == 1
        assert isinstance(middleware[0], RoundRobinModelMiddleware)
