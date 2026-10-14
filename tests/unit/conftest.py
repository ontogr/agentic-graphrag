"""Keeps unit tests off a developer's repository-root ``.env``.

The settings classes read ``.env`` relative to the working directory, so a
``.env`` in the directory a test runs from can point the test at a configured
LLM endpoint. When a ``.env`` is visible from the working directory, each unit
test runs from an empty temporary directory instead. Environment variables are
left alone, so a test that sets its own is unaffected. With no ``.env`` present
(as in CI) this fixture does nothing.
"""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _run_without_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run the test from an empty directory when a ``.env`` is visible.

    Args:
        monkeypatch: Pytest fixture that restores the working directory after the test.
        tmp_path: An empty directory unique to this test.
    """
    if Path(".env").exists():
        monkeypatch.chdir(tmp_path)
