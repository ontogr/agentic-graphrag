"""Provider-agnostic LLM client configuration, shared by every LLM-backed role."""

from typing import Any, Literal

from pydantic import BaseModel, Field


LLMProvider = Literal[
    "anthropic",
    "aws-bedrock",
    "google-ai",
    "vertex-ai",
    "openai",
    "openai-responses",
    "azure-openai",
    "openai-generic",
]


class LLMClientConfig(BaseModel):
    """One named LLM client's connection config.

    Attributes:
        name: A unique name for this client within its registry.
        provider: The BAML provider backend this client uses.
        model: The model identifier the provider expects.
        api_key: The API key, when the provider needs one directly (not via ambient
            cloud credentials, as aws-bedrock and vertex-ai typically use).
        base_url: A custom endpoint, required for ``openai-generic`` and optional
            elsewhere.
        options: Provider-specific fields with no common shape across providers
            (Azure's ``resource_name``/``deployment_id``, Vertex's ``project``,
            Bedrock's ``region``).
    """

    name: str
    provider: LLMProvider
    model: str
    api_key: str | None = None
    base_url: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class RetryConfig(BaseModel):
    """Exponential backoff retry settings for an LLM client.

    Attributes:
        max_retries: The maximum number of retry attempts.
        delay_ms: The initial delay before the first retry.
        multiplier: The backoff multiplier applied after each retry.
        max_delay_ms: The maximum delay between retries.
    """

    max_retries: int = Field(default=3, ge=0)
    delay_ms: int = Field(default=200, ge=0)
    multiplier: float = Field(default=1.5, ge=0)
    max_delay_ms: int = Field(default=10_000, ge=0)
