"""Select CI workloads from the files changed in a GitHub event."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path


OUTPUTS = (
    "python_lint",
    "typing",
    "unit",
    "backend_tests",
    "wheel",
    "api_docs",
    "docs_pins",
    "docs_build",
    "snippets",
    "typos",
    "workflow_audit",
    "bandit",
    "dependency_audit",
)

ALL = dict.fromkeys(OUTPUTS, True)
SHARED_PYTHON_INPUTS = {"pyproject.toml", "uv.lock", "Makefile"}
POLICY_PATHS = {
    "AGENTS.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "LICENSE",
    "CODE_OF_CONDUCT.md",
    "README.md",
}
SKILL_OR_RESEARCH_PATHS = (
    ".agents/skills/",
    ".claude/skills/",
    "thoughts/",
)
NO_TEST_PATHS = POLICY_PATHS | {".pre-commit-config.yaml"}
KNOWN_ROOT_FILES = (
    POLICY_PATHS
    | SHARED_PYTHON_INPUTS
    | {
        ".pre-commit-config.yaml",
        ".gitignore",
        ".gitleaks.toml",
        ".python-version",
        "codecov.yml",
        "cliff.toml",
    }
)
DOCS_BUILD_PATHS = {
    "docs/docusaurus.config.js",
    "docs/sidebars.js",
    "docs/package.json",
    "docs/package-lock.json",
    "docs/versions.json",
}


def classify(paths: Iterable[str], *, force_all: bool = False) -> dict[str, bool]:
    """Select workloads for changed paths, defaulting to all on unknown paths."""
    if force_all:
        return ALL.copy()
    selected = dict.fromkeys(OUTPUTS, False)
    selected["typos"] = True
    path_list = list(paths)
    if not path_list:
        return ALL.copy()

    for path in path_list:
        _classify_path(path, selected)

    return selected


def _self_test() -> None:
    """Check representative classification cases for the Actions entry point."""
    cases = {
        (".claude/skills/example/SKILL.md",): {
            "typos": True,
            "unit": False,
            "backend_tests": False,
            "wheel": False,
        },
        ("README.md",): {"typos": True, "wheel": True},
        ("CHANGELOG.md",): {"docs_build": True},
        ("LICENSE",): {"typos": True, "wheel": True},
        (".github/workflows/docs.yml",): {
            "docs_build": True,
            "workflow_audit": True,
            "docs_pins": False,
        },
        (".github/scripts/docs_api_links.py",): {
            "unit": True,
            "api_docs": True,
            "docs_build": True,
        },
        ("docs/src/css/site.css",): {"docs_build": True, "snippets": False},
        ("docs/docs/guides/example.mdx",): {
            "docs_build": True,
            "snippets": True,
        },
        ("docs/conftest.py",): {
            "python_lint": True,
            "snippets": True,
            "unit": False,
        },
        ("tests/unit/test_x.py",): {
            "unit": True,
            "typing": True,
            "backend_tests": False,
        },
        ("tests/integration/test_x.py",): {"unit": True, "backend_tests": True},
        ("docker/docker-compose.ci.yml",): {"backend_tests": True, "snippets": True},
        ("unknown-root/file",): dict.fromkeys(OUTPUTS, True),
        (".github/scripts/new_helper.py",): dict.fromkeys(OUTPUTS, True),
        ("docker/backend-config.yml",): dict.fromkeys(OUTPUTS, True),
        ("examples/helper.py",): dict.fromkeys(OUTPUTS, True),
        (".claude/settings.json",): dict.fromkeys(OUTPUTS, True),
    }
    for paths, expected in cases.items():
        selected = classify(paths)
        for name, value in expected.items():
            if selected[name] is not value:
                raise AssertionError(f"{paths!r}: expected {name}={value}")
    for path in (
        "docs/versioned_docs/version-0.1.0/intro.md",
        "docs/navbarIcons.js",
    ):
        if not classify([path])["docs_build"]:
            raise AssertionError(f"docs changes must build the site: {path}")
    scheduled = classify([".claude/skills/example/SKILL.md"], force_all=True)
    if scheduled != ALL:
        raise AssertionError("scheduled runs must select every workload")


def _classify_path(path: str, selected: dict[str, bool]) -> None:
    if path in SHARED_PYTHON_INPUTS or path == ".github/scripts/ci_changes.py":
        selected.update(ALL)
    else:
        _classify_specific_path(path, selected)


def _classify_specific_path(path: str, selected: dict[str, bool]) -> None:
    if path in {"README.md", "LICENSE"}:
        selected.update(typos=True, wheel=True)
    elif path == "CHANGELOG.md":
        selected.update(typos=True, docs_build=True)
    elif path.startswith(".github/workflows/"):
        _select_workflow_checks(path, selected)
    elif _is_skill_path(path) or path.startswith(SKILL_OR_RESEARCH_PATHS):
        _classify_non_test_path(path, selected)
    elif path == ".github/scripts/update_precommit_docs_pins.py":
        selected.update(unit=True, docs_pins=True, python_lint=True)
    elif path in NO_TEST_PATHS:
        _classify_non_test_path(path, selected)
    elif path == "docs/conftest.py":
        selected.update(python_lint=True, snippets=True)
    elif path == "docker/docker-compose.ci.yml":
        selected.update(backend_tests=True, snippets=True)
    elif path.startswith("tests/unit/"):
        selected["unit"] = True
        if path.endswith((".py", ".ipynb")):
            selected.update(python_lint=True, typing=True)
    elif path.startswith("agrag/llm/baml_client/"):
        _select_package(selected)
    else:
        _select_general_path(path, selected)


def _is_skill_path(path: str) -> bool:
    return path.startswith((".github/skills/", ".agents/skills/", ".claude/skills/"))


def _select_general_path(path: str, selected: dict[str, bool]) -> None:
    _select_code_checks(path, selected)
    _select_test_checks(path, selected)
    _select_docs_checks(path, selected)
    _select_security_checks(path, selected)
    if not _is_known_path(path):
        print(f"Unknown path selects all workloads: {path!r}", file=sys.stderr)
        selected.update(ALL)


def _classify_non_test_path(path: str, selected: dict[str, bool]) -> None:
    if path in POLICY_PATHS or path.startswith(SKILL_OR_RESEARCH_PATHS):
        selected["typos"] = True
    if path == ".pre-commit-config.yaml":
        selected["docs_pins"] = True
    if not _is_known_path(path):
        print(f"Unknown path selects all workloads: {path!r}", file=sys.stderr)
        selected.update(ALL)


def _select_workflow_checks(path: str, selected: dict[str, bool]) -> None:
    selected["workflow_audit"] = True
    if path.endswith(("ci.yml", "changes.yml", "integration.yml", "docs-snippets.yml")):
        selected.update(ALL)
    elif path.endswith(("docs.yml", "preview.yml")):
        selected.update(docs_build=True, snippets=True)


def _select_code_checks(path: str, selected: dict[str, bool]) -> None:
    if path.endswith((".py", ".ipynb")):
        selected["python_lint"] = True
    if path.startswith(("agrag/", "benchmarks/")) or (
        path.startswith("tests/") and not path.startswith("tests/unit/")
    ):
        selected["typing"] = True
    if path.startswith(("agrag/", "benchmarks/", "tests/")):
        selected["unit"] = True
    if path.startswith("agrag/"):
        _select_package(selected)


def _select_test_checks(path: str, selected: dict[str, bool]) -> None:
    if path.startswith(("tests/integration/", "tests/fixtures/")) or (
        path.startswith("tests/")
        and (
            path == "tests/conftest.py"
            or path.endswith("/__init__.py")
            or path.count("/") <= 2
        )
    ):
        selected["backend_tests"] = True


def _select_docs_checks(path: str, selected: dict[str, bool]) -> None:
    if path.startswith("docs/") or path in DOCS_BUILD_PATHS:
        selected["docs_build"] = True
    if path.startswith("docs/docs/api/") and path != "docs/docs/api/index.md":
        selected["api_docs"] = True
    if path == ".github/scripts/docs_api_links.py":
        selected.update(unit=True, api_docs=True, docs_build=True)
    if path == ".github/scripts/update_precommit_docs_pins.py":
        selected.update(unit=True, docs_pins=True)
    if path == ".pre-commit-config.yaml":
        selected["docs_pins"] = True
    if (
        path.startswith(("docs/docs/get-started/", "docs/docs/guides/"))
        or path == "docs/conftest.py"
    ):
        selected["snippets"] = True


def _select_security_checks(path: str, selected: dict[str, bool]) -> None:
    if path.startswith("agrag/"):
        selected["bandit"] = True
    if path in SHARED_PYTHON_INPUTS:
        selected["dependency_audit"] = True


def _select_package(selected: dict[str, bool]) -> None:
    selected.update(
        typing=True,
        unit=True,
        backend_tests=True,
        wheel=True,
        api_docs=True,
        docs_build=True,
        snippets=True,
        bandit=True,
    )


def _is_known_path(path: str) -> bool:
    if path.startswith(".github/"):
        return path.startswith((".github/workflows/", ".github/skills/")) or path in {
            ".github/scripts/ci_changes.py",
            ".github/scripts/docs_api_links.py",
            ".github/scripts/update_precommit_docs_pins.py",
        }
    if path.startswith((".agents/", ".claude/")):
        return _is_skill_path(path) or path.startswith("thoughts/")
    known_prefixes = (
        "agrag/",
        "benchmarks/",
        "tests/",
        "docs/",
        "thoughts/",
        "reports/",
    )
    return (
        path.startswith(known_prefixes)
        or path == "docker/docker-compose.ci.yml"
        or path in {"examples/demo.py", "examples/quickstart.py"}
        or path in KNOWN_ROOT_FILES
    )


def changed_paths(event: dict[str, object]) -> tuple[list[str], str]:
    """Read changed paths from an event payload and the local Git history."""
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    if event_name in {"schedule", "workflow_dispatch"}:
        return [], "scheduled or manually dispatched run"

    if event_name == "pull_request":
        return _pull_request_paths(event)

    if event_name == "push":
        return _push_paths(event)

    raise ValueError(f"unsupported event type {event_name!r}")


def _pull_request_paths(event: dict[str, object]) -> tuple[list[str], str]:
    pull_request = event.get("pull_request")
    if not isinstance(pull_request, dict):
        raise ValueError("pull_request event is missing its pull_request object")
    base, head = pull_request.get("base"), pull_request.get("head")
    if not isinstance(base, dict) or not isinstance(head, dict):
        raise ValueError("pull_request event is missing base or head commit data")
    base_sha, head_sha = base.get("sha"), head.get("sha")
    if not isinstance(base_sha, str) or not isinstance(head_sha, str):
        raise ValueError("pull_request event is missing base or head SHA")
    if not base_sha or not head_sha:
        raise ValueError("pull_request event contains an empty base or head SHA")
    merge_base = _git("merge-base", base_sha, head_sha)
    return _diff_paths(merge_base, head_sha), f"PR merge-base {merge_base[:12]}"


def _push_paths(event: dict[str, object]) -> tuple[list[str], str]:
    before, after = event.get("before"), event.get("after")
    if not isinstance(before, str) or not isinstance(after, str):
        raise ValueError("push event is missing before or after SHA")
    if not before or not after:
        raise ValueError("push event contains an empty before or after SHA")
    if set(before) == {"0"}:
        return [], "new branch push has no previous commit"
    return _diff_paths(before, after), f"push {before[:12]}..{after[:12]}"


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _diff_paths(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "-z", "--no-renames", base, head, "--"],
        check=True,
        capture_output=True,
    )
    return [
        path.decode("utf-8", errors="surrogateescape")
        for path in result.stdout.split(b"\0")
        if path
    ]


def main() -> int:
    """Write workload outputs to GitHub Actions, using all workloads on uncertainty."""
    if sys.argv[1:] == ["--self-test"]:
        _self_test()
        print("CI selector checks passed")
        return 0

    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        event, event_error = {}, "GITHUB_EVENT_PATH is not set"
    else:
        try:
            event = json.loads(Path(event_path).read_text())
            event_error = None
        except (OSError, json.JSONDecodeError) as error:
            event, event_error = {}, str(error)

    try:
        if event_error is not None:
            raise ValueError(event_error)
        if not isinstance(event, dict):
            raise ValueError("event payload must be a JSON object")
        paths, reason = changed_paths(event)
        selected = classify(paths, force_all=event_name_requires_all())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Could not determine changed paths; selecting all workloads: {error}")
        paths, reason, selected = [], "changed paths unavailable", ALL.copy()

    print(f"Selection basis: {reason}")
    for path in paths:
        print(f"Changed: {path!r}")
    print("Selected: " + ", ".join(key for key, value in selected.items() if value))

    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        raise ValueError("GITHUB_OUTPUT is not set")
    try:
        with Path(output_path).open("a") as output:
            for key, value in selected.items():
                output.write(f"{key}={'true' if value else 'false'}\n")
    except OSError as error:
        print(f"Could not write outputs to GITHUB_OUTPUT: {error}", file=sys.stderr)
        return 1
    return 0


def event_name_requires_all() -> bool:
    """Return whether the current event should run all workloads."""
    return os.environ.get("GITHUB_EVENT_NAME") in {"schedule", "workflow_dispatch"}


if __name__ == "__main__":
    raise SystemExit(main())
