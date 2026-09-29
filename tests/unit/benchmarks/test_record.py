"""Tests the run record: code identity, destinations and stable JSON.

The identity tests build a throwaway git repository, so they need the git binary
and nothing else.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from benchmarks.harness.record import (
    RunRecord,
    code_identity,
    run_directory,
    write_record,
)
from benchmarks.harness.runner import RunOptions, run
from tests.unit.benchmarks.fakes import DOMAIN, Behaviour, make_code, make_environment


def _git(root: Path, *args: str) -> None:
    # A pre-commit hook exports GIT_* variables that would point git at the
    # outer repository instead of the throwaway one.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=root,
        check=True,
        capture_output=True,
        env=env,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A git repository with agrag/, benchmarks/ and uv.lock, all committed."""
    root = tmp_path / "repo"
    (root / "agrag").mkdir(parents=True)
    (root / "benchmarks" / "results").mkdir(parents=True)
    (root / "agrag" / "a.py").write_text("x = 1\n")
    (root / "benchmarks" / "b.py").write_text("y = 1\n")
    (root / "uv.lock").write_text("lock\n")
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "init")
    return root


class TestCodeIdentity:
    """Code identity read from a throwaway git repository."""

    def test_clean_tree_is_not_dirty(self, repo):
        """Clean tree is not dirty."""
        assert code_identity(repo).git_dirty is False

    def test_committing_a_run_does_not_make_the_next_run_dirty(self, repo):
        """Committing a run does not make the next run dirty."""
        (repo / "benchmarks" / "results" / "lite").mkdir()
        (repo / "benchmarks" / "results" / "lite" / "record.json").write_text("{}")

        assert code_identity(repo).git_dirty is False

    def test_edit_to_agrag_or_benchmarks_code_is_dirty(self, repo):
        """Edit to agrag or benchmarks code is dirty."""
        (repo / "benchmarks" / "b.py").write_text("y = 2\n")

        assert code_identity(repo).git_dirty is True

    def test_agrag_tree_hash_changes_with_agrag_code_only(self, repo):
        """Agrag tree hash changes with agrag code only."""
        before = code_identity(repo)
        (repo / "benchmarks" / "b.py").write_text("y = 2\n")
        _git(repo, "commit", "-qam", "bench")
        after_bench = code_identity(repo)
        (repo / "agrag" / "a.py").write_text("x = 2\n")
        _git(repo, "commit", "-qam", "agrag")
        after_agrag = code_identity(repo)

        assert after_bench.agrag_tree == before.agrag_tree
        assert after_bench.benchmarks_code_sha256 != before.benchmarks_code_sha256
        assert after_agrag.agrag_tree != before.agrag_tree

    def test_results_do_not_change_the_benchmarks_code_hash(self, repo):
        """Results do not change the benchmarks code hash."""
        before = code_identity(repo)
        (repo / "benchmarks" / "results" / "x.json").write_text("{}")
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", "results")

        assert (
            code_identity(repo).benchmarks_code_sha256 == before.benchmarks_code_sha256
        )


class TestWriteRecord:
    """Where a record is written and how its JSON looks."""

    async def _record(self, tmp_path, *, dirty: bool) -> RunRecord:
        env, _ = make_environment(tmp_path, Behaviour(), code=make_code(dirty=dirty))
        record, _ = await run(
            "fake",
            DOMAIN,
            "lite",
            RunOptions(max_llm_calls=1000, max_tokens=100_000),
            env,
        )
        return record

    async def test_refuses_a_dirty_record_under_results(self, tmp_path):
        """Refuses a dirty record under results."""
        record = await self._record(tmp_path, dirty=True)

        with pytest.raises(ValueError, match="dirty"):
            write_record(
                record,
                tmp_path / "results" / "lite" / "x",
                results=tmp_path / "results",
            )

    async def test_sends_dirty_runs_to_reports_and_clean_runs_to_results(
        self, tmp_path
    ):
        """Sends dirty runs to reports and clean runs to results."""
        dirty = await self._record(tmp_path / "a", dirty=True)
        clean = await self._record(tmp_path / "b", dirty=False)
        results, reports = tmp_path / "results", tmp_path / "reports"

        assert run_directory(dirty, results=results, reports=reports).is_relative_to(
            reports
        )
        assert run_directory(clean, results=results, reports=reports).is_relative_to(
            results
        )

    async def test_json_has_sorted_keys_and_floats_rounded_to_four_places(
        self, tmp_path
    ):
        """Json has sorted keys and floats rounded to four places."""
        record = await self._record(tmp_path, dirty=False)
        record.usage.wall_seconds = 1.234567
        path = write_record(record, tmp_path / "out", results=tmp_path / "results")

        payload = json.loads(path.read_text())

        assert payload["usage"]["wall_seconds"] == 1.2346
        assert list(payload) == sorted(payload)
