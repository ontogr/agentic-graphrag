"""Tests for EvalJudgeSettings.

Covers the ``EVAL_JUDGE_*`` variables, their fallback to ``LLM_*``, the missing
model id error, and the empty-temperature switch. ``load_dotenv`` is patched
and the working directory is empty, so the repository ``.env`` cannot satisfy
a fallback.
"""

from pathlib import Path

import pytest

from agrag.eval.settings import EvalJudgeSettings


_VARIABLES = (
    "EVAL_JUDGE_BASE_URL",
    "EVAL_JUDGE_API_KEY",
    "EVAL_JUDGE_MODEL_ID",
    "EVAL_JUDGE_TEMPERATURE",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL_ID",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Remove every judge and LLM variable and hide the repository .env."""
    for name in _VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("agrag.eval.settings.load_dotenv", lambda *a, **k: None)


class TestEvalJudgeSettings:
    """EvalJudgeSettings resolves the judge client from the environment."""

    def test_uses_eval_judge_variables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """EVAL_JUDGE_* wins over LLM_*."""
        monkeypatch.setenv("EVAL_JUDGE_BASE_URL", "http://judge/v1")
        monkeypatch.setenv("EVAL_JUDGE_API_KEY", "judge-key")
        monkeypatch.setenv("EVAL_JUDGE_MODEL_ID", "judge-model")
        monkeypatch.setenv("LLM_MODEL_ID", "agent-model")

        client = EvalJudgeSettings.from_openai_compatible_env().client

        assert client.model == "judge-model"
        assert client.base_url == "http://judge/v1"
        assert client.api_key == "judge-key"
        assert client.provider == "openai-generic"

    def test_falls_back_to_llm_variables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLM_* configures the judge when EVAL_JUDGE_* is unset."""
        monkeypatch.setenv("LLM_BASE_URL", "http://agent/v1")
        monkeypatch.setenv("LLM_API_KEY", "agent-key")
        monkeypatch.setenv("LLM_MODEL_ID", "agent-model")

        client = EvalJudgeSettings.from_openai_compatible_env().client

        assert client.model == "agent-model"
        assert client.base_url == "http://agent/v1"
        assert client.api_key == "agent-key"

    def test_falls_back_when_eval_judge_variables_are_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty EVAL_JUDGE_* value falls back to LLM_*, like an unset one."""
        monkeypatch.setenv("EVAL_JUDGE_MODEL_ID", "")
        monkeypatch.setenv("LLM_MODEL_ID", "agent-model")

        client = EvalJudgeSettings.from_openai_compatible_env().client

        assert client.model == "agent-model"

    def test_raises_without_a_model_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No model id, or an empty one, is an error, never a default."""
        monkeypatch.setenv("LLM_MODEL_ID", "")

        with pytest.raises(ValueError, match="model id"):
            EvalJudgeSettings.from_openai_compatible_env()

    def test_temperature_defaults_to_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The judge runs at temperature 0 unless told otherwise."""
        monkeypatch.setenv("LLM_MODEL_ID", "m")

        assert EvalJudgeSettings.from_openai_compatible_env().temperature == 0.0

    @pytest.mark.parametrize(("raw", "expected"), [("", None), ("0.3", 0.3)])
    def test_reads_temperature_from_env(
        self, monkeypatch: pytest.MonkeyPatch, raw: str, expected: float | None
    ) -> None:
        """An empty EVAL_JUDGE_TEMPERATURE means no temperature."""
        monkeypatch.setenv("LLM_MODEL_ID", "m")
        monkeypatch.setenv("EVAL_JUDGE_TEMPERATURE", raw)

        assert EvalJudgeSettings.from_openai_compatible_env().temperature == expected
