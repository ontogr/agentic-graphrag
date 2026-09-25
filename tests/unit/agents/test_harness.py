"""Tests for the DeepAgents harness profile registration.

Mocks ``register_harness_profile`` at the deepagents boundary and asserts
the per-provider dedup and that importing the module never requires
deepagents to be installed.
"""

import subprocess
import sys
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from agrag.agents.harness import (
    _HARNESS_PROFILE_REGISTERED,
    ensure_harness_profile,
)


@pytest.fixture(autouse=True)
def _clean_guard() -> Iterator[None]:
    """Isolate registration-guard changes made by each test."""
    previous = set(_HARNESS_PROFILE_REGISTERED)
    _HARNESS_PROFILE_REGISTERED.clear()
    yield
    _HARNESS_PROFILE_REGISTERED.clear()
    _HARNESS_PROFILE_REGISTERED.update(previous)


class TestHarness:
    """Tests DeepAgents profile registration and provider-key mapping."""

    def test_registers_once_per_provider(self) -> None:
        """A second call for the same provider is a no-op."""
        register = MagicMock()
        monkeydeep = MagicMock(
            HarnessProfile=MagicMock(),
            GeneralPurposeSubagentProfile=MagicMock(),
            register_harness_profile=register,
        )
        original = sys.modules.get("deepagents")
        sys.modules["deepagents"] = monkeydeep
        try:
            ensure_harness_profile("openai")
            ensure_harness_profile("openai")
        finally:
            if original is None:
                del sys.modules["deepagents"]
            else:
                sys.modules["deepagents"] = original

        assert register.call_count == 1

    def test_registers_separately_per_distinct_provider(self) -> None:
        """Each provider gets its own first registration."""
        register = MagicMock()
        monkeydeep = MagicMock(
            HarnessProfile=MagicMock(),
            GeneralPurposeSubagentProfile=MagicMock(),
            register_harness_profile=register,
        )
        original = sys.modules.get("deepagents")
        sys.modules["deepagents"] = monkeydeep
        try:
            ensure_harness_profile("openai")
            ensure_harness_profile("anthropic")
        finally:
            if original is None:
                del sys.modules["deepagents"]
            else:
                sys.modules["deepagents"] = original

        assert register.call_count == 2
        registered_keys = [call.args[0] for call in register.call_args_list]
        assert registered_keys == ["openai", "anthropic"]

    def test_importable_without_deepagents_installed(self) -> None:
        """Importing the module never imports deepagents."""
        code = (
            "import sys\n"
            "sys.modules['deepagents'] = None\n"
            "import agrag.agents.harness\n"
            "print('ok')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )
        assert "ok" in result.stdout
        assert result.returncode == 0
