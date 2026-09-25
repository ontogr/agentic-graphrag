"""Env-backed configuration for the eval judge model."""

from typing import Annotated

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from agrag.llm.client_config import LLMClientConfig


class _JudgeEnvVariables(BaseSettings):
    """Resolve the judge's OpenAI-compatible connection variables.

    Reads each ``EVAL_JUDGE_*``/``LLM_*`` pair as two separate fields rather
    than one aliased field, because ``AliasChoices`` stops at the first alias
    present in the environment even when its value is empty. Falling back to
    ``LLM_*`` on an empty ``EVAL_JUDGE_*`` needs the ``or`` in the properties
    below.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    eval_judge_base_url: str | None = Field(
        default=None, validation_alias="EVAL_JUDGE_BASE_URL"
    )
    llm_base_url: str | None = Field(default=None, validation_alias="LLM_BASE_URL")
    eval_judge_api_key: str | None = Field(
        default=None, validation_alias="EVAL_JUDGE_API_KEY"
    )
    llm_api_key: str | None = Field(default=None, validation_alias="LLM_API_KEY")
    eval_judge_model_id: str | None = Field(
        default=None, validation_alias="EVAL_JUDGE_MODEL_ID"
    )
    llm_model_id: str | None = Field(default=None, validation_alias="LLM_MODEL_ID")

    @property
    def base_url(self) -> str | None:
        """Return the judge base URL, falling back to the shared LLM one."""
        return self.eval_judge_base_url or self.llm_base_url

    @property
    def api_key(self) -> str | None:
        """Return the judge API key, falling back to the shared LLM one."""
        return self.eval_judge_api_key or self.llm_api_key

    @property
    def model_id(self) -> str | None:
        """Return the judge model id, falling back to the shared LLM one."""
        return self.eval_judge_model_id or self.llm_model_id


class EvalJudgeSettings(BaseSettings):
    """LLM client config for the eval judge.

    Attributes:
        client: The judge model's client config.
        temperature: The sampling temperature the judge sends. ``None`` sends
            none, for models that reject the parameter. Set
            ``EVAL_JUDGE_TEMPERATURE`` empty to get ``None``.
            Env: ``EVAL_JUDGE_TEMPERATURE``.

    Env prefix: ``EVAL_JUDGE_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="EVAL_JUDGE_", env_file=".env", extra="ignore"
    )

    client: LLMClientConfig
    temperature: Annotated[float | None, NoDecode] = 0.0

    @field_validator("temperature", mode="before")
    @classmethod
    def _empty_temperature_is_none(cls, value: object) -> object:
        """Read an empty string as no temperature."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @classmethod
    def from_openai_compatible_env(cls) -> "EvalJudgeSettings":
        """Build settings from OpenAI-compatible env vars.

        Loads ``.env`` first, then resolves ``EVAL_JUDGE_BASE_URL``,
        ``EVAL_JUDGE_API_KEY`` and ``EVAL_JUDGE_MODEL_ID`` through
        pydantic-settings. Each falls back to the shared ``LLM_*`` variable
        when unset or empty, so the judge is the agent's own model unless
        ``EVAL_JUDGE_*`` is set. That model grades its own answers, which
        biases scores upward. There is no default model.

        Returns:
            EvalJudgeSettings with one openai-generic client.

        Raises:
            ValueError: No model id resolves from either set of variables.
        """
        load_dotenv()
        variables = _JudgeEnvVariables()
        if not variables.model_id:
            raise ValueError(
                "No judge model id: set EVAL_JUDGE_MODEL_ID or LLM_MODEL_ID."
            )
        return cls(
            client=LLMClientConfig(
                name="eval-judge",
                provider="openai-generic",
                model=variables.model_id,
                api_key=variables.api_key or "",
                base_url=variables.base_url or "",
            )
        )
