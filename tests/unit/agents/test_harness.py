"""Tests for the DeepAgents harness profile registration.

Mocks ``register_harness_profile`` at the deepagents boundary and asserts
the per-provider dedup, the profile's exact shape, and that importing the
module never requires deepagents to be installed.
"""

import subprocess
import sys
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from agrag.agents.harness import (
    _HARNESS_PROFILE_REGISTERED,
    ensure_harness_profile,
    model_provider_key,
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

    def test_excluded_tools_and_general_purpose_subagent_disabled(self) -> None:
        """The registered profile excludes execute and disables the subagent."""
        captured: dict = {}

        def fake_register(key: str, profile: object) -> None:
            captured["key"] = key
            captured["profile"] = profile

        profile_cls = MagicMock()
        gp_instance = MagicMock()
        gp_instance.enabled = False
        profile_cls.GeneralPurposeSubagentProfile.return_value = gp_instance
        profile_cls.HarnessProfile = MagicMock(side_effect=lambda **kwargs: kwargs)
        monkeydeep = MagicMock(
            HarnessProfile=profile_cls.HarnessProfile,
            GeneralPurposeSubagentProfile=profile_cls.GeneralPurposeSubagentProfile,
            register_harness_profile=fake_register,
        )
        original = sys.modules.get("deepagents")
        sys.modules["deepagents"] = monkeydeep
        try:
            ensure_harness_profile("openai")
        finally:
            if original is None:
                del sys.modules["deepagents"]
            else:
                sys.modules["deepagents"] = original

        assert captured["key"] == "openai"
        assert captured["profile"]["excluded_tools"] == frozenset({"execute"})
        assert (
            profile_cls.GeneralPurposeSubagentProfile.call_args.kwargs["enabled"]
            is False
        )

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

    @pytest.mark.parametrize(
        ("provider", "expected_key"),
        [
            ("anthropic", "anthropic"),
            ("openai", "openai"),
            ("openai-generic", "openai"),
            ("google-ai", "google_genai"),
        ],
    )
    def test_maps_supported_provider_to_harness_key(
        self, provider: str, expected_key: str
    ) -> None:
        """Each supported configured provider uses its harness key."""
        assert model_provider_key(provider) == expected_key
