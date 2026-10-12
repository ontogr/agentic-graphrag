"""Check that changed paths select the CI workloads that own them."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


_SCRIPT = Path(__file__).parents[2] / ".github" / "scripts" / "ci_changes.py"
_SPEC = importlib.util.spec_from_file_location("ci_changes", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
ci_changes = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ci_changes)


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (
            [".claude/skills/custom/SKILL.md"],
            {"python_lint": False, "backend_tests": False, "typos": True},
        ),
        (["docs/src/css/custom.css"], {"docs_build": True, "snippets": False}),
        (["docs/docs/guides/example.mdx"], {"docs_build": True, "snippets": True}),
        (["docs/conftest.py"], {"python_lint": True, "snippets": True, "unit": False}),
        (["agrag/module.py"], {"backend_tests": True, "bandit": True, "wheel": True}),
        (
            ["agrag/llm/baml_client/generated.py"],
            {"python_lint": False, "backend_tests": True},
        ),
        (
            ["tests/unit/example.py"],
            {"unit": True, "typing": True, "backend_tests": False},
        ),
        (["tests/integration/example.py"], {"unit": True, "backend_tests": True}),
        (["tests/fixtures/sample.json"], {"unit": True, "backend_tests": True}),
        (
            ["benchmarks/example.py"],
            {"typing": True, "unit": True, "backend_tests": False},
        ),
        (
            [".github/scripts/docs_api_links.py"],
            {
                "python_lint": True,
                "unit": True,
                "api_docs": True,
                "docs_build": True,
            },
        ),
        (
            ["docs/docs/api/generated.md"],
            {"api_docs": True, "docs_build": True, "snippets": False},
        ),
        (
            ["docs/docs/api/index.md"],
            {"api_docs": False, "docs_build": True},
        ),
        ([".pre-commit-config.yaml"], {"docs_pins": True, "unit": False}),
        (
            [".github/scripts/update_precommit_docs_pins.py"],
            {"docs_pins": True, "unit": True, "python_lint": True},
        ),
        (["LICENSE"], {"wheel": True, "typos": True}),
        (["README.md"], {"wheel": True, "typos": True}),
        (["CHANGELOG.md"], {"docs_build": True}),
        ([".python-version"], dict.fromkeys(ci_changes.OUTPUTS, True)),
        ([".github/scripts/new_helper.py"], dict.fromkeys(ci_changes.OUTPUTS, True)),
        (["docker/backend-config.yml"], dict.fromkeys(ci_changes.OUTPUTS, True)),
        (["examples/helper.py"], dict.fromkeys(ci_changes.OUTPUTS, True)),
        ([".claude/settings.json"], dict.fromkeys(ci_changes.OUTPUTS, True)),
        (
            [".github/workflows/docs.yml"],
            {"docs_build": True, "workflow_audit": True, "docs_pins": False},
        ),
        (["docker/docker-compose.ci.yml"], {"backend_tests": True, "snippets": True}),
        (["unknown-root/new_file.txt"], dict.fromkeys(ci_changes.OUTPUTS, True)),
    ],
)
def test_changed_paths_select_expected_workloads(
    paths: list[str], expected: dict[str, bool]
) -> None:
    """Paths select their owning checks without hiding unknown changes."""
    selected = ci_changes.classify(paths)

    for workload, value in expected.items():
        assert selected[workload] is value


def test_empty_path_list_selects_every_workload() -> None:
    """An absent changed-file set cannot be treated as a safe no-op."""
    assert ci_changes.classify([]) == ci_changes.ALL


def test_deleted_and_renamed_paths_are_classified_independently() -> None:
    """Old and new sides of a rename retain their separate check ownership."""
    selected = ci_changes.classify(
        ["docs/docs/guides/removed.mdx", ".claude/skills/new/SKILL.md"]
    )

    assert selected["snippets"] is True
    assert selected["backend_tests"] is False


def test_paths_with_newlines_remain_single_classification_inputs() -> None:
    """A path delimiter inside a filename does not create a second path."""
    selected = ci_changes.classify([".claude/skills/line\nbreak/SKILL.md"])

    assert selected["backend_tests"] is False
    assert selected["unit"] is False


@pytest.mark.parametrize(
    "path",
    [
        "docs/versioned_docs/version-0.1.0/intro.md",
        "docs/navbarIcons.js",
    ],
)
def test_docs_site_inputs_select_docs_build(path: str) -> None:
    """Versioned pages and imported site config files trigger a site build."""
    assert ci_changes.classify([path])["docs_build"] is True


@pytest.mark.parametrize("event_name", ["push", "pull_request"])
def test_event_diff_preserves_both_sides_of_a_rename(
    tmp_path: Path, event_name: str
) -> None:
    """The CLI selects snippets when a guide moves into a skills directory."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    guide = tmp_path / "docs/docs/guides/example.mdx"
    guide.parent.mkdir(parents=True)
    guide.write_text("Example guide\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    commit_command = [
        "git",
        "-c",
        "user.name=CI test",
        "-c",
        "user.email=ci@example.com",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        "Add guide",
    ]
    subprocess.run(commit_command, cwd=tmp_path, check=True)
    base = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True
    ).strip()
    skill = tmp_path / ".claude/skills/line\nbreak/SKILL.md"
    skill.parent.mkdir(parents=True)
    guide.rename(skill)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(commit_command, cwd=tmp_path, check=True)
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True
    ).strip()
    event = (
        {"before": base, "after": head}
        if event_name == "push"
        else {"pull_request": {"base": {"sha": base}, "head": {"sha": head}}}
    )
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))
    output_path = tmp_path / "outputs"

    subprocess.run(
        [sys.executable, str(_SCRIPT)],
        cwd=tmp_path,
        env={
            **os.environ,
            "GITHUB_EVENT_NAME": event_name,
            "GITHUB_EVENT_PATH": str(event_path),
            "GITHUB_OUTPUT": str(output_path),
        },
        check=True,
    )

    outputs = dict(line.split("=") for line in output_path.read_text().splitlines())
    assert outputs["snippets"] == "true"
    assert outputs["docs_build"] == "true"
    assert outputs["backend_tests"] == "false"
    assert outputs["unit"] == "false"


@pytest.mark.parametrize(
    "payload", ["[]", "{", '{"before": "missing", "after": "missing"}']
)
def test_cli_selects_all_when_event_or_history_is_unavailable(
    tmp_path: Path, payload: str
) -> None:
    """Bad event data and unavailable Git commits cannot silently skip checks."""
    event_path = tmp_path / "event.json"
    event_path.write_text(payload)
    output_path = tmp_path / "outputs"

    subprocess.run(
        [sys.executable, str(_SCRIPT)],
        cwd=tmp_path,
        env={
            **os.environ,
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_EVENT_PATH": str(event_path),
            "GITHUB_OUTPUT": str(output_path),
        },
        check=True,
    )

    outputs = dict(line.split("=") for line in output_path.read_text().splitlines())
    assert len(outputs) == 13
    assert set(outputs.values()) == {"true"}
