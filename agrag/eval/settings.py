"""Env-backed configuration for the eval judge model."""

import os
from typing import Annotated

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from agrag.llm.client_config import LLMClientConfig


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

        Loads ``.env`` first, then reads ``EVAL_JUDGE_BASE_URL``,
        ``EVAL_JUDGE_API_KEY`` and ``EVAL_JUDGE_MODEL_ID``. Each falls back to
        the shared ``LLM_*`` variable when unset, so the judge is the agent's
        own model unless ``EVAL_JUDGE_*`` is set. That model grades its own
        answers, which biases scores upward. There is no default model.

        Returns:
            EvalJudgeSettings with one openai-generic client.

        Raises:
            ValueError: No model id resolves from either set of variables.
        """
        load_dotenv()
        base_url = os.environ.get("EVAL_JUDGE_BASE_URL") or os.environ.get(
            "LLM_BASE_URL"
        )
        api_key = os.environ.get("EVAL_JUDGE_API_KEY") or os.environ.get("LLM_API_KEY")
        model = os.environ.get("EVAL_JUDGE_MODEL_ID") or os.environ.get("LLM_MODEL_ID")
        if not model:
            raise ValueError(
                "No judge model id: set EVAL_JUDGE_MODEL_ID or LLM_MODEL_ID."
            )
        return cls(
            client=LLMClientConfig(
                name="eval-judge",
                provider="openai-generic",
                model=model,
                api_key=api_key or "",
                base_url=base_url or "",
            )
        )
