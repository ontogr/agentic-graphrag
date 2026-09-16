"""Guard the docs generation toolchain against version drift.

The docs-api pre-commit hook regenerates docs/docs/api/index.md inside its own
pinned hook environment, while developers and CI regenerate the same file with
``uv run --group docs griffe2md``, which resolves whatever ``uv.lock`` pins.
These two paths diverge silently when the lockfile resolves a different
version of one of the toolchain packages, so ``git diff --exit-code`` can
report stale-docs failures that do not reproduce locally (or vice versa).

These tests fail when a docs-api hook pin no longer matches the version
``uv.lock`` resolves, so the two generation paths cannot drift.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import yaml


DOCS_DEPS_PINS = ("griffe2md", "chonkie")

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PIN_RE = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s,;]+)$")


def _load_lock_versions() -> dict[str, str]:
    """Read the locked version of every package in ``uv.lock``.

    Returns:
        Mapping of normalized package name to locked version.
    """
    with (REPO_ROOT / "uv.lock").open("rb") as handle:
        lock = tomllib.load(handle)
    return {package["name"].lower(): package["version"] for package in lock["package"]}


def _load_hook_pins() -> dict[str, str]:
    """Read the docs-api hook ``additional_dependencies`` pins.

    Returns:
        Mapping of normalized package name to pinned version.
    """
    with (REPO_ROOT / ".pre-commit-config.yaml").open() as handle:
        config = yaml.safe_load(handle)
    for repo in config["repos"]:
        for hook in repo.get("hooks", []):
            if hook.get("id") == "docs-api":
                pins = {}
                for dep in hook.get("additional_dependencies", []):
                    match = HOOK_PIN_RE.match(dep)
                    assert match is not None, (
                        f"docs-api pin is not name==version: {dep!r}"
                    )
                    name, version = match.groups()
                    pins[name.lower()] = version
                return pins
    raise AssertionError("docs-api hook not found in .pre-commit-config.yaml")


class TestDocsToolchainPins:
    """The docs-api hook pins must mirror the lockfile versions."""

    def test_hook_pins_track_docs_toolchain(self) -> None:
        """Every toolchain package has one corresponding hook pin."""
        pins = _load_hook_pins()
        assert sorted(pins) == sorted(DOCS_DEPS_PINS)

    def test_hook_pins_match_uv_lock(self) -> None:
        """Hook pins stay in sync with the versions ``uv.lock`` resolves."""
        lock_versions = _load_lock_versions()
        for name, pinned in _load_hook_pins().items():
            assert name in lock_versions, f"{name} missing from uv.lock"
            assert pinned == lock_versions[name], (
                f"docs-api hook pins {name}=={pinned} "
                f"but uv.lock resolves {lock_versions[name]}"
            )
