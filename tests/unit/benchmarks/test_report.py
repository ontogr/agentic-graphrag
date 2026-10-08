"""Tests the report table: newest record per key, all records, model warning."""

from agrag.chunking import Chunker
from benchmarks.harness.record import RunRecord
from benchmarks.harness.report import load_records, report
from benchmarks.harness.runner import RunOptions, run
from tests.unit.benchmarks.fakes import DOMAIN, Behaviour, make_environment


async def _record(tmp_path, *, model: str, created_at: str, chunk_size: int = 1000):
    env, _ = make_environment(
        tmp_path,
        Behaviour(),
        models={
            "agent": {"model_id": model, "provider": "p"},
            "judge": {"model_id": "judge", "provider": "p", "temperature": 0.0},
            "extractor": {"model_id": model, "provider": "p"},
            "embedder": {"model": "e"},
        },
        chunking=Chunker(size=chunk_size),
    )
    record, _ = await run(
        "fake", DOMAIN, "lite", RunOptions(max_llm_calls=1000, max_tokens=10**6), env
    )
    return record.model_copy(update={"created_at": created_at})


def _rows(table: str) -> list[str]:
    return [line for line in table.splitlines() if line.startswith("| fake")]


class TestReport:
    """Selection of records and warnings in the report table."""

    def test_empty_results_print_only_the_header(self, tmp_path):
        """Empty results print only the header."""
        table = report(load_records(tmp_path))

        assert table.splitlines()[0].startswith("| domain")
        assert _rows(table) == []

    async def test_shows_the_newest_record_of_each_key(self, tmp_path):
        """Shows the newest record of each key."""
        old = await _record(tmp_path / "a", model="m", created_at="2026-01-01T00:00:00")
        new = await _record(tmp_path / "b", model="m", created_at="2026-02-01T00:00:00")

        rows = _rows(report([old, new]))

        assert len(rows) == 1
        assert "2026-02-01" in rows[0]

    async def test_all_lists_every_record(self, tmp_path):
        """All lists every record."""
        old = await _record(tmp_path / "a", model="m", created_at="2026-01-01T00:00:00")
        new = await _record(tmp_path / "b", model="m", created_at="2026-02-01T00:00:00")

        assert len(_rows(report([old, new], show_all=True))) == 2

    async def test_runs_at_other_chunking_are_kept_apart(self, tmp_path):
        """Runs at other chunking are kept apart."""
        first = await _record(
            tmp_path / "a", model="m", created_at="2026-01-01T00:00:00"
        )
        other = await _record(
            tmp_path / "b", model="m", created_at="2026-02-01T00:00:00", chunk_size=500
        )

        assert len(_rows(report([first, other]))) == 2

    async def test_warns_when_a_domain_has_runs_on_more_than_one_model(self, tmp_path):
        """Warns when a domain has runs on more than one model."""
        one = await _record(
            tmp_path / "a", model="m1", created_at="2026-01-01T00:00:00"
        )
        two = await _record(
            tmp_path / "b", model="m2", created_at="2026-02-01T00:00:00"
        )

        assert "fake has runs on 2 model pairs" in report([one, two])

    async def test_loads_records_from_a_results_tree(self, tmp_path):
        """Loads records from a results tree."""
        record = await _record(tmp_path, model="m", created_at="2026-01-01T00:00:00")

        loaded = load_records(tmp_path / "results")

        assert [r.run_id for r in loaded] == [record.run_id]
        assert isinstance(loaded[0], RunRecord)
