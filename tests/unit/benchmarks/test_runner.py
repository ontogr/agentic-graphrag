"""Runs the fake domain through the whole runner with fake services and stores.

The fake system emits LLM spans, so usage in the record comes from the same span
path a real run uses. No test calls a model, Docker or Neo4j.
"""

import gzip
import json

import pytest

from benchmarks.datasets.base import Domain
from benchmarks.harness import dry_run as dry_run_module
from benchmarks.harness.config import SpendCap
from benchmarks.harness.dry_run import SpendCapError
from benchmarks.harness.record import RunRecord
from benchmarks.harness.runner import (
    InfrastructureError,
    RunOptions,
    RunRefusedError,
    run,
)
from benchmarks.harness.trace import upload_trace
from tests.unit.benchmarks.fakes import (
    DOMAIN,
    SCHEMA,
    Behaviour,
    FakeAdapter,
    FakeStore,
    FakeSystem,
    llm_span,
    make_code,
    make_environment,
)


def options(**changes) -> RunOptions:
    """Return run options with a cap that the fake domain fits under."""
    values = {"max_llm_calls": 1000, "max_tokens": 100_000, "question_timeout_s": 1}
    return RunOptions(**{**values, **changes})


class TestRunner:
    """One run of the fake domain: usage, failures, caps and destinations."""

    async def test_writes_one_corpus_entry_per_corpus_and_sums_usage_by_path(
        self, tmp_path
    ):
        """Writes one corpus entry per corpus and sums usage by path."""
        behaviour = Behaviour()
        env, commands = make_environment(tmp_path, behaviour)

        record, path = await run("fake", DOMAIN, "lite", options(), env)

        assert [c.corpus_id for c in record.corpora] == ["c1", "c2"]
        by_path = record.usage.by_path
        assert by_path["extraction"].llm_calls == 4
        assert by_path["extraction"].input_tokens == 400
        assert by_path["other"].llm_calls == 2
        assert by_path["agent"].llm_calls == 4
        assert by_path["judge"].llm_calls == 4
        assert record.usage.llm_calls == 14
        assert record.corpora[0].ingest_usage.llm_calls == 3
        assert all(q.llm_calls == 1 for q in record.questions)
        assert commands.verbs().count("stop") == 2
        loaded = RunRecord.model_validate_json(path.read_text())
        assert loaded.run_id == record.run_id
        assert loaded.scores == record.scores
        assert loaded.trace == record.trace

    async def test_passes_every_message_of_a_multi_turn_question(self, tmp_path):
        """Passes every message of a multi turn question."""
        behaviour = Behaviour()
        env, _ = make_environment(tmp_path, behaviour)

        await run("fake", DOMAIN, "lite", options(), env)

        multi_turn = next(q for q in behaviour.asked if q.id == "q12")
        assert [m["role"] for m in multi_turn.messages] == [
            "user",
            "assistant",
            "user",
        ]
        assert multi_turn.query == "second"

    async def test_second_run_hits_the_cache_and_copies_ingest_usage(self, tmp_path):
        """Second run hits the cache and copies ingest usage."""
        behaviour = Behaviour()
        env, commands = make_environment(tmp_path, behaviour)
        first, _ = await run("fake", DOMAIN, "lite", options(), env)
        behaviour.ingests.clear()

        second, _ = await run("fake", DOMAIN, "lite", options(), env)

        assert behaviour.ingests == []
        assert all(c.ingest_cache_hit for c in second.corpora)
        assert second.corpora[0].ingest_usage == first.corpora[0].ingest_usage
        assert second.usage.by_path["extraction"].llm_calls == 0

    async def test_changed_agrag_tree_rebuilds_the_service_and_reingests(
        self, tmp_path
    ):
        """Changed agrag tree rebuilds the service and reingests."""
        behaviour = Behaviour()
        env, commands = make_environment(tmp_path, behaviour)
        await run("fake", DOMAIN, "lite", options(), env)
        behaviour.ingests.clear()
        commands.calls.clear()
        env.code = make_code(tree="tree2")

        record, _ = await run("fake", DOMAIN, "lite", options(), env)

        assert behaviour.ingests == ["c1", "c2"]
        assert not any(c.ingest_cache_hit for c in record.corpora)
        assert commands.verbs().count("down") == 2

    async def test_dirty_tree_never_uses_the_cache(self, tmp_path):
        """Dirty tree never uses the cache."""
        behaviour = Behaviour()
        env, _ = make_environment(tmp_path, behaviour, code=make_code(dirty=True))
        await run("fake", DOMAIN, "lite", options(), env)
        behaviour.ingests.clear()

        record, _ = await run("fake", DOMAIN, "lite", options(), env)

        assert behaviour.ingests == ["c1", "c2"]
        assert not any(c.ingest_cache_hit for c in record.corpora)

    async def test_failed_ingest_closes_the_store_and_stops_the_service(self, tmp_path):
        """Failed ingest closes the store and stops the service."""
        behaviour = Behaviour()
        env, commands = make_environment(tmp_path, behaviour)
        opened: list[FakeStore] = []
        open_store = env.open_store

        def tracking_open(settings, tracer):
            opened.append(open_store(settings, tracer))
            return opened[-1]

        class BrokenIngest(FakeSystem):
            async def ingest(self) -> None:
                raise RuntimeError("ingest failed")

        env.open_store = tracking_open
        env.make_system = lambda context: BrokenIngest(context, behaviour)

        with pytest.raises(InfrastructureError):
            await run("fake", DOMAIN, "lite", options(retries=0), env)

        assert commands.verbs()[-1] == "stop"
        assert all(store.closed for store in opened)

    async def test_failure_before_the_system_exists_closes_the_store(self, tmp_path):
        """Failure before the system exists closes the store and stops the service."""
        env, commands = make_environment(tmp_path, Behaviour())
        opened: list[FakeStore] = []
        open_store = env.open_store

        def tracking_open(settings, tracer):
            opened.append(open_store(settings, tracer))
            return opened[-1]

        def broken(_context):
            raise RuntimeError("no system")

        env.open_store = tracking_open
        env.make_system = broken

        with pytest.raises(RuntimeError, match="no system"):
            await run("fake", DOMAIN, "lite", options(), env)

        assert commands.verbs()[-1] == "stop"
        assert all(store.closed for store in opened)

    async def test_teardown_failure_still_stops_the_service(self, tmp_path):
        """A failing teardown does not leave the corpus service running."""
        behaviour = Behaviour()
        env, commands = make_environment(tmp_path, behaviour)

        class BrokenTeardown(FakeSystem):
            async def teardown(self) -> None:
                raise RuntimeError("teardown failed")

        env.make_system = lambda context: BrokenTeardown(context, behaviour)

        with pytest.raises(RuntimeError, match="teardown failed"):
            await run("fake", DOMAIN, "lite", options(), env)

        assert commands.verbs()[-1] == "stop"

    async def test_corpora_sharing_a_schema_name_keep_both_schemas(self, tmp_path):
        """Schemas that share a name but differ in version are both recorded."""
        env, _ = make_environment(tmp_path, Behaviour())

        class Versioned(FakeAdapter):
            def schema(self, corpus):
                return SCHEMA.model_copy(update={"version": corpus.id})

        domain = Domain(adapter=Versioned(), grader=DOMAIN.grader)

        record, _ = await run("fake", domain, "lite", options(), env)

        assert [(s.name, s.version) for s in record.schemas] == [
            ("fake", "c1"),
            ("fake", "c2"),
        ]

    async def test_agent_failure_and_timeout_score_zero_and_are_flagged(self, tmp_path):
        """Agent failure and timeout score zero and are flagged."""
        behaviour = Behaviour()
        behaviour.agent_failures = {"q11"}
        behaviour.slow = {"q21"}
        env, _ = make_environment(tmp_path, behaviour)

        record, _ = await run(
            "fake", DOMAIN, "lite", options(question_timeout_s=0.05), env
        )

        by_id = {q.id: q for q in record.questions}
        assert by_id["q11"].status == "agent_failure"
        assert by_id["q11"].scores == {"correctness": 0.0}
        assert by_id["q21"].status == "agent_failure"
        assert by_id["q21"].flags == ["timeout"]
        assert by_id["q12"].scores == {"correctness": 1.0}
        assert record.scores.aggregate["correctness"].n == 4
        assert record.scores.aggregate["correctness"].mean == 0.5

    async def test_infrastructure_error_retries_then_aborts_without_a_record(
        self, tmp_path
    ):
        """Infrastructure error retries then aborts without a record."""
        behaviour = Behaviour()
        behaviour.infra_error = ConnectionError("429")
        env, _ = make_environment(tmp_path, behaviour)

        with pytest.raises(InfrastructureError):
            await run("fake", DOMAIN, "lite", options(), env)

        assert not list(tmp_path.rglob("record.json"))

    async def test_spend_cap_stops_the_run_before_any_call(self, tmp_path):
        """Spend cap stops the run before any call."""
        behaviour = Behaviour()
        env, commands = make_environment(tmp_path, behaviour)

        with pytest.raises(SpendCapError, match="above the cap"):
            await run("fake", DOMAIN, "lite", options(max_llm_calls=1), env)

        assert commands.calls == []
        assert behaviour.asked == []

    async def test_run_without_a_cap_is_refused(self, tmp_path):
        """Run without a cap is refused."""
        env, _ = make_environment(tmp_path, Behaviour())

        with pytest.raises(SpendCapError, match="no spend cap"):
            await run("fake", DOMAIN, "lite", RunOptions(question_timeout_s=1), env)

    async def test_configured_cap_is_used_and_flags_override_it(
        self, tmp_path, monkeypatch
    ):
        """Configured cap is used and flags override it."""
        monkeypatch.setitem(
            dry_run_module.SPEND_CAPS, ("fake", "lite"), SpendCap(1000, 100_000)
        )
        env, _ = make_environment(tmp_path, Behaviour())

        plain, _ = await run(
            "fake", DOMAIN, "lite", RunOptions(question_timeout_s=1), env
        )
        overridden, _ = await run("fake", DOMAIN, "lite", options(), env)

        assert plain.usage.spend_cap.overridden is False
        assert overridden.usage.spend_cap.overridden is True

    async def test_dirty_tree_writes_to_reports_and_never_to_results(self, tmp_path):
        """Dirty tree writes to reports and never to results."""
        env, _ = make_environment(tmp_path, Behaviour(), code=make_code(dirty=True))

        record, path = await run("fake", DOMAIN, "lite", options(), env)

        assert path.is_relative_to(tmp_path / "reports")
        assert not (tmp_path / "results").exists()
        assert record.trace is not None

    async def test_incomplete_usage_writes_to_reports(self, tmp_path):
        """Incomplete usage writes to reports."""
        behaviour = Behaviour()
        env, _ = make_environment(tmp_path, behaviour)
        original = env.make_system

        def system_with_missing_usage(context):
            llm_span(context.tracer, prompt=None)
            return original(context)

        env.make_system = system_with_missing_usage

        record, path = await run("fake", DOMAIN, "lite", options(), env)

        assert record.usage.usage_complete is False
        assert path.is_relative_to(tmp_path / "reports")

    async def test_clean_lite_run_commits_record_and_trace_to_results(self, tmp_path):
        """Clean lite run commits record and trace to results."""
        env, _ = make_environment(tmp_path, Behaviour())

        record, path = await run("fake", DOMAIN, "lite", options(), env)

        assert path == tmp_path / "results" / "lite" / record.run_id / "record.json"
        trace = path.parent / "trace.jsonl.gz"
        with gzip.open(trace, "rt") as handle:
            batches = [json.loads(line) for line in handle]
        assert batches
        assert record.trace.path == "trace.jsonl.gz"

    async def test_runs_started_in_the_same_minute_keep_separate_records(
        self, tmp_path
    ):
        """Runs started in the same minute keep separate records."""
        env, _ = make_environment(tmp_path, Behaviour())

        first, first_path = await run("fake", DOMAIN, "lite", options(), env)
        second, second_path = await run("fake", DOMAIN, "lite", options(), env)

        assert first.run_id != second.run_id
        assert first_path.exists()
        assert second_path.exists()


class TestFullMode:
    """Full-mode guards: trace repo, confirmation and trace upload."""

    async def test_refuses_to_start_without_a_trace_repo(self, tmp_path):
        """Refuses to start without a trace repo."""
        env, commands = make_environment(tmp_path, Behaviour(), trace_repo=None)

        with pytest.raises(RunRefusedError, match="BENCH_TRACE_REPO"):
            await run("fake", DOMAIN, "full", options(yes=True), env)

        assert commands.calls == []

    async def test_declined_confirmation_stops_before_any_call(self, tmp_path):
        """Declined confirmation stops before any call."""
        env, commands = make_environment(
            tmp_path, Behaviour(), trace_repo="me/traces", confirm=lambda _: False
        )

        with pytest.raises(RunRefusedError, match="declined"):
            await run("fake", DOMAIN, "full", options(), env)

        assert commands.calls == []

    async def test_yes_skips_the_prompt_and_uploads_the_trace_first(self, tmp_path):
        """Yes skips the prompt and uploads the trace first."""
        uploads = []

        def upload(path, *, repo, run_id):
            uploads.append((repo, run_id, path.exists()))
            return upload_trace(path, repo=repo, run_id=run_id, api=_FakeApi())

        env, _ = make_environment(
            tmp_path, Behaviour(), trace_repo="me/traces", upload=upload
        )

        record, path = await run("fake", DOMAIN, "full", options(yes=True), env)

        assert uploads == [("me/traces", record.run_id, True)]
        assert record.trace.repo == "me/traces"
        assert record.trace.revision == "rev1"
        assert not (path.parent / "trace.jsonl.gz").exists()

    async def test_failed_upload_aborts_and_keeps_files_in_reports(self, tmp_path):
        """Failed upload aborts and keeps files in reports."""

        def upload(path, *, repo, run_id):
            raise OSError("offline")

        env, _ = make_environment(
            tmp_path, Behaviour(), trace_repo="me/traces", upload=upload
        )

        with pytest.raises(OSError, match="offline"):
            await run("fake", DOMAIN, "full", options(yes=True), env)

        assert not (tmp_path / "results").exists()
        assert list((tmp_path / "reports").rglob("trace.jsonl.gz"))


class _FakeApi:
    """A stand-in for ``HfApi`` that records nothing and returns a revision."""

    def create_repo(self, *args, **kwargs) -> None:
        """Accept the call."""

    def upload_file(self, **kwargs):
        """Return a commit with a fixed id."""

        class Commit:
            oid = "rev1"

        return Commit()
