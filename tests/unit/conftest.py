"""Keeps unit tests off a developer's LLM configuration.

The settings classes read ``.env`` relative to the working directory, so a
``.env`` in the directory a test runs from can point the test at a configured
LLM endpoint. When a ``.env`` is visible from the working directory, each unit
test runs from an empty temporary directory instead. The BAML default client
reads ``OPENAI_API_KEY`` from the environment, so that variable is removed for
each test. Other environment variables are left alone. With no ``.env`` present
(as in CI) only the environment variable is removed.
"""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _run_without_llm_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Hide the repository ``.env`` and the shell OpenAI key from a unit test.

    Args:
        monkeypatch: Pytest fixture that restores the environment and working
            directory after the test.
        tmp_path: An empty directory unique to this test.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    if Path(".env").exists():
        monkeypatch.chdir(tmp_path)
