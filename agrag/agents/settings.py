"""Env-backed LLM and loop config for the agent layer."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from agrag.llm.client_config import LLMClientConfig


class AgentLLMSettings(BaseSettings):
    """LLM client config for the agent's own reasoning turns.

    Mirrors ExtractionLLMSettings for the agent role: same shape,
    same from_openai_compatible_env() convention, because the
    agent's model and the extraction model are configured the same
    way even though the agent calls its model through LangChain,
    not BAML.

    Attributes:
        clients: The LLM client(s) to use. One element for a single
            provider; more than one composed per strategy through
            agent middleware.
        strategy: How to compose multiple clients. ``"fallback"``
            tries the other clients in order when a model call fails;
            ``"round_robin"`` rotates across all clients per call.
            Ignored with one client.

    Env prefix: ``AGENT_LLM_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="AGENT_LLM_", env_file=".env", extra="ignore"
    )

    clients: list[LLMClientConfig]
    strategy: Literal["single", "fallback", "round_robin"] = "single"

    @classmethod
    def from_openai_compatible_env(cls) -> "AgentLLMSettings":
        """Build settings from OpenAI-compatible env vars.

        Reads ``AGENT_LLM_BASE_URL``, ``AGENT_LLM_API_KEY``, and
        ``AGENT_LLM_MODEL_ID`` from the environment.

        Returns:
            AgentLLMSettings with one openai-generic client.
        """
        import os  # noqa: PLC0415

        base_url = os.environ.get("AGENT_LLM_BASE_URL", "")
        api_key = os.environ.get("AGENT_LLM_API_KEY", "")
        model = os.environ.get("AGENT_LLM_MODEL_ID", "gpt-4o-mini")

        return cls(
            clients=[
                LLMClientConfig(
                    name="agent",
                    provider="openai-generic",
                    model=model,
                    api_key=api_key,
                    base_url=base_url,
                )
            ],
            strategy="single",
        )


class AgentSettings(BaseSettings):
    """Configuration for the agent loop itself.

    Attributes:
        recursion_limit: The maximum LangGraph step count before
            the loop stops and reports incomplete progress.

    Env prefix: ``AGENT_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="AGENT_", env_file=".env", extra="ignore"
    )

    recursion_limit: int = 50
