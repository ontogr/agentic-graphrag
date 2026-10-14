"""Blanks LLM settings for every unit test.

Environment variables take precedence over the repo-root ``.env`` in
pydantic-settings, so an empty value here keeps unit tests from reaching a
configured LLM endpoint even when ``.env`` sets one. The ``*_CLIENTS`` fields
are JSON lists and cannot be blanked, so they are set to an empty list instead.
"""

import pytest


_LLM_ENV_VARS = (
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL_ID",
    "AGENT_LLM_BASE_URL",
    "AGENT_LLM_API_KEY",
    "AGENT_LLM_MODEL_ID",
    "EVAL_JUDGE_BASE_URL",
    "EVAL_JUDGE_API_KEY",
    "EVAL_JUDGE_MODEL_ID",
    "OPENAI_API_KEY",
)
_LLM_CLIENT_LIST_ENV_VARS = ("EXTRACTION_LLM_CLIENTS", "AGENT_LLM_CLIENTS")


@pytest.fixture(autouse=True)
def _blank_llm_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blank LLM settings for the duration of a test.

    Args:
        monkeypatch: Pytest fixture that restores the environment after the test.
    """
    for name in _LLM_ENV_VARS:
        monkeypatch.setenv(name, "")
    for name in _LLM_CLIENT_LIST_ENV_VARS:
        monkeypatch.setenv(name, "[]")
