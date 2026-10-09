"""The runner: ingest each corpus in its own service, answer, grade, write a record."""

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar
from uuid import uuid4

from opentelemetry.trace import Tracer

from agrag.chunking import Chunker
from agrag.common.data_models.document import Document
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.graphdb import GraphStore, Neo4jGraphStore, Neo4jSettings
from benchmarks.datasets.base import Domain
from benchmarks.grading.base import Grader, aggregate
from benchmarks.harness import cache
from benchmarks.harness.config import COST_MODEL, CostModel
from benchmarks.harness.dry_run import DryRun, check_cap, dry_run
from benchmarks.harness.record import (
    REPORTS_DIR,
    RESULTS_DIR,
    TRACE_NAME,
    ChunkingInfo,
    CodeIdentity,
    CorpusRecord,
    DatasetInfo,
    GraphStats,
    ModelsInfo,
    PathUsage,
    QuestionRecord,
    RunConfig,
    RunRecord,
    SchemaInfo,
    SpendCapRecord,
    TraceRef,
    UsageRecord,
    run_directory,
    write_record,
)
from benchmarks.harness.services import Services, neo4j_settings
from benchmarks.harness.trace import upload_trace
from benchmarks.harness.usage import (
    CORPUS_ATTRIBUTE,
    GRADE_SPAN,
    INGEST_SPAN,
    QUESTION_ATTRIBUTE,
    QUESTION_SPAN,
    Tracing,
    start_tracing,
    summarize,
)
from benchmarks.models import (
    BenchmarkQuestion,
    Corpus,
    CorpusManifest,
    Mode,
    canonical_sha256,
)
from benchmarks.systems.base import AgentFailureError, SystemAdapter, SystemAnswer


_T = TypeVar("_T")


class InfrastructureError(Exception):
    """A provider, network or service error that survived the retries.

    The run aborts and writes no record.
    """


class RunRefusedError(Exception):
    """The run cannot start, or the owner declined it."""


@dataclass
class RunOptions:
    """Per-run limits from the command line.

    Attributes:
        concurrency: Questions answered at once.
        question_timeout_s: The seconds one question may take. A timeout is an agent
            failure.
        max_llm_calls: Replaces the spend cap on calls for this run.
        max_tokens: Replaces the spend cap on tokens for this run.
        yes: Skips the confirmation of a full run.
        seed: The seed the record states.
        retries: The retries of an infrastructure error, before the run aborts.
        backoff_s: The first wait between retries, doubled each time.
    """

    concurrency: int = 2
    question_timeout_s: float = 900.0
    max_llm_calls: int | None = None
    max_tokens: int | None = None
    yes: bool = False
    seed: int = 42
    retries: int = 3
    backoff_s: float = 2.0


@dataclass
class SystemContext:
    """What a system needs to serve one corpus."""

    corpus: Corpus
    schema: GraphSchema
    store: GraphStore
    documents: Sequence[Document]
    tracer: Tracer


def open_neo4j(settings: Neo4jSettings, tracer: Tracer) -> GraphStore:
    """Open the graph store of a service."""
    return Neo4jGraphStore(settings=settings, tracer=tracer)


@dataclass
class RunEnvironment:
    """The parts of a run that tests replace.

    Attributes:
        system_name: The name in the run id and the record.
        code: The identity of the code.
        chunking: The chunking every document gets.
        models: The model ids and settings, for the record.
        agent_config: The agent loop settings, for the record.
        make_system: Builds the system for one corpus.
        make_judge: Builds the judge around the tracer.
        services: The compose services.
        confirm: Asks the owner to confirm a full run.
        trace_repo: The Hugging Face dataset repo for full-run traces.
        cost: The measured cost model.
        open_store: Opens the graph store of a service.
        upload: Uploads a trace and returns its reference.
        sleep: Waits between retries.
        results_dir: The committed results root.
        reports_dir: The ignored root for runs that are not committed.
        embedder_model: The embedder model id.
    """

    system_name: str
    code: CodeIdentity
    chunking: Chunker
    models: ModelsInfo
    agent_config: dict[str, Any]
    make_system: Callable[[SystemContext], SystemAdapter]
    make_judge: Callable[[Tracer], Any]
    services: Services = field(default_factory=Services)
    confirm: Callable[[DryRun], bool] = lambda _bound: False
    trace_repo: str | None = None
    cost: CostModel | None = COST_MODEL
    open_store: Callable[[Neo4jSettings, Tracer], GraphStore] = open_neo4j
    upload: Callable[..., TraceRef] = upload_trace
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    results_dir: Path = RESULTS_DIR
    reports_dir: Path = REPORTS_DIR
    embedder_model: str = ""


@dataclass
class _Outcome:
    """The result of answering one question."""

    question: BenchmarkQuestion
    answer: SystemAnswer | None
    latency_s: float
    flags: list[str] = field(default_factory=list)


@dataclass
class _Context:
    """The shared state of one run."""

    options: RunOptions
    env: RunEnvironment
    tracing: Tracing


async def _retry(
    call: Callable[[], Awaitable[_T]],
    ctx: _Context,
    passthrough: tuple[type[Exception], ...] = (),
) -> _T:
    """Run ``call``, retrying an error with backoff, then abort the run.

    LangChain, the provider SDKs and BAML retry below this layer, so the harness
    retries only errors that reach it, and only ``options.retries`` times. Errors
    of the ``passthrough`` types are not retried.

    Raises:
        InfrastructureError: The call kept failing.
    """
    options = ctx.options
    for attempt in range(options.retries + 1):
        try:
            return await call()
        except passthrough:
            raise
        except Exception as error:
            if attempt == options.retries:
                raise InfrastructureError(f"{type(error).__name__}: {error}") from error
            await ctx.env.sleep(options.backoff_s * 2**attempt)
    raise AssertionError("unreachable")


async def _answer_question(
    system: SystemAdapter, question: BenchmarkQuestion, ctx: _Context
) -> _Outcome:
    """Answer one question under its own span.

    A failure of the agent or a timeout gives an outcome without an answer.
    """
    started = time.monotonic()

    async def call() -> SystemAnswer:
        return await asyncio.wait_for(
            system.answer(question), ctx.options.question_timeout_s
        )

    with ctx.tracing.tracer.start_as_current_span(
        QUESTION_SPAN, attributes={QUESTION_ATTRIBUTE: question.id}
    ):
        try:
            answer = await _retry(
                call, ctx, passthrough=(AgentFailureError, TimeoutError)
            )
        except TimeoutError:
            flags = ["timeout"]
        except AgentFailureError:
            flags = []
        else:
            return _Outcome(question, answer, time.monotonic() - started)
    return _Outcome(question, None, time.monotonic() - started, flags)


@dataclass
class _Serving:
    """What a corpus service holds open, so the caller can release it on failure."""

    store: GraphStore | None = None
    system: SystemAdapter | None = None

    async def release(self) -> None:
        """Tear down the system, or close the store when no system exists."""
        if self.system is not None:
            await self.system.teardown()
        elif self.store is not None:
            await self.store.close()


async def _ingest_corpus(
    corpus: Corpus,
    documents: Sequence[Document],
    schema: GraphSchema,
    key: str,
    ctx: _Context,
    *,
    serving: _Serving,
) -> tuple[SystemAdapter, cache.IngestMarker, bool, GraphStats]:
    """Start the corpus service, ingest unless the cache matches, build the system.

    A marker with another key, or no marker, means the graph may not match the
    corpus, so the service is removed and rebuilt before ingest. A run from a
    dirty tree never uses the cache, because the key names only committed code.

    ``serving`` receives the open store and the system as they come to exist.

    Returns:
        The system, the ingest marker, whether the cache hit, and the graph counts.

    """
    env, tracer = ctx.env, ctx.tracing.tracer
    settings = neo4j_settings(corpus.service)
    env.services.up(corpus.service)
    store = serving.store = env.open_store(settings, tracer)
    await store.connect()
    marker = await cache.read_marker(store)
    hit = not env.code.git_dirty and marker is not None and marker.key == key
    if not hit:
        serving.store = None
        await store.close()
        env.services.remove(corpus.service)
        env.services.up(corpus.service)
        store = serving.store = env.open_store(settings, tracer)
        await store.connect()
    system = serving.system = env.make_system(
        SystemContext(corpus, schema, store, documents, tracer)
    )
    labels = [entity.label for entity in schema.entities]
    relation_types = [relation.label for relation in schema.relations]
    if marker is not None and hit:
        stats = await cache.graph_stats(
            store, labels=labels, relation_types=relation_types
        )
        return system, marker, True, stats

    with tracer.start_as_current_span(
        INGEST_SPAN, attributes={CORPUS_ATTRIBUTE: corpus.id}
    ):
        await _retry(system.ingest, ctx)
    spans = summarize(ctx.tracing.memory.get_finished_spans()).by_corpus.get(corpus.id)
    marker = cache.IngestMarker(
        key,
        spans.usage if spans else PathUsage(),
        spans.empty_extractions if spans else 0,
    )
    await cache.write_marker(store, marker)
    stats = await cache.graph_stats(store, labels=labels, relation_types=relation_types)
    return system, marker, False, stats


async def _execute(
    manifest: CorpusManifest,
    domain: Domain,
    documents: dict[str, Sequence[Document]],
    bound: DryRun,
    ctx: _Context,
) -> tuple[list[CorpusRecord], list[SchemaInfo], list[_Outcome]]:
    """Ingest and answer each corpus in turn, stopping its service after it."""
    env = ctx.env
    corpora: list[CorpusRecord] = []
    schemas: list[SchemaInfo] = []
    outcomes: list[_Outcome] = []
    for corpus in manifest.corpora:
        schema = domain.adapter.schema(corpus)
        info = SchemaInfo(
            name=schema.name,
            version=schema.version,
            sha256=canonical_sha256(schema.model_dump(mode="json")),
        )
        if info not in schemas:
            schemas.append(info)
        key = cache.cache_key(
            manifest=manifest,
            corpus_id=corpus.id,
            schema_sha256=info.sha256,
            extractor_model=env.models["extractor"]["model_id"],
            embedder_model=env.embedder_model,
            chunking_fingerprint=env.chunking.fingerprint,
            agrag_tree=env.code.agrag_tree,
            benchmarks_code_sha256=env.code.benchmarks_code_sha256,
            uv_lock_sha256=env.code.uv_lock_sha256,
        )
        serving = _Serving()
        try:
            system, marker, hit, stats = await _ingest_corpus(
                corpus, documents[corpus.id], schema, key, ctx, serving=serving
            )
            questions = [q for q in manifest.questions if q.corpus_id == corpus.id]
            outcomes.extend(
                await _bounded(
                    ctx.options.concurrency,
                    questions,
                    lambda q, system=system: _answer_question(system, q, ctx),
                )
            )
            corpora.append(
                CorpusRecord(
                    corpus_id=corpus.id,
                    service=corpus.service,
                    n_documents=len(corpus.documents),
                    corpus_tokens=corpus.n_tokens,
                    chunks=bound.chunks[corpus.id],
                    cache_key=key,
                    ingest_cache_hit=hit,
                    ingest_usage=marker.usage,
                    empty_extractions=marker.empty_extractions,
                    graph=stats,
                )
            )
        finally:
            try:
                await serving.release()
            finally:
                env.services.stop(corpus.service)
    return corpora, schemas, outcomes


async def _grade(
    outcome: _Outcome, grader: Grader, judge: Any, ctx: _Context
) -> QuestionRecord:
    """Score one outcome. An agent failure scores 0 on every metric."""
    question = outcome.question
    answer = outcome.answer
    if answer is None:
        return QuestionRecord(
            id=question.id,
            corpus_id=question.corpus_id,
            group=question.group,
            latency_s=outcome.latency_s,
            status="agent_failure",
            flags=outcome.flags,
            scores=dict.fromkeys(grader.metrics, 0.0),
        )

    async def call():
        with ctx.tracing.tracer.start_as_current_span(GRADE_SPAN):
            return await grader.grade(question, answer, judge)

    grade = await _retry(call, ctx)
    return QuestionRecord(
        id=question.id,
        corpus_id=question.corpus_id,
        group=question.group,
        latency_s=outcome.latency_s,
        status="ok",
        flags=grade.flags,
        scores=grade.scores,
    )


async def _bounded(
    limit: int, items: Sequence[Any], work: Callable[[Any], Awaitable[_T]]
) -> list[_T]:
    """Run ``work`` over ``items``, at most ``limit`` at once, in item order.

    The first failure cancels the rest and is raised on its own.
    """
    gate = asyncio.Semaphore(limit)

    async def one(item: Any) -> _T:
        async with gate:
            return await work(item)

    try:
        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(one(item)) for item in items]
    except* InfrastructureError as errors:
        raise errors.exceptions[0] from None
    return [task.result() for task in tasks]


@dataclass
class Plan:
    """What a run will do and the bound on its cost.

    Attributes:
        manifest: The manifest of the run.
        documents: The documents of each corpus, by corpus id.
        bound: The bound on calls and tokens.
        cap: The spend cap the estimate passed.
    """

    manifest: CorpusManifest
    documents: dict[str, Sequence[Document]]
    bound: DryRun
    cap: SpendCapRecord


def make_plan(
    name: str,
    domain: Domain,
    mode: Mode,
    options: RunOptions,
    *,
    chunking: Chunker,
    cost: CostModel | None,
) -> Plan:
    """Load a domain, estimate its cost and check the spend cap. Calls no model.

    Raises:
        RunRefusedError: No measured cost model exists.
        SpendCapError: The estimate is above the cap, or no cap exists.
    """
    if cost is None:
        raise RunRefusedError("no measured cost model: set COST_MODEL in config")
    manifest = domain.adapter.load(mode)
    documents = {c.id: domain.adapter.documents(c) for c in manifest.corpora}
    bound = dry_run(
        manifest,
        documents,
        chunking=chunking,
        cost=cost,
        judge_calls_per_question=domain.grader_for(mode).judge_calls_per_question,
    )
    cap = check_cap(
        bound,
        name,
        mode,
        max_llm_calls=options.max_llm_calls,
        max_tokens=options.max_tokens,
    )
    return Plan(manifest, documents, bound, cap)


async def run(
    name: str,
    domain: Domain,
    mode: Mode,
    options: RunOptions,
    env: RunEnvironment,
) -> tuple[RunRecord, Path]:
    """Run one domain in one mode and write its record.

    A full run refuses to start without a trace repo. The run bounds its cost,
    checks the spend cap and, in full mode, asks for confirmation. Then, for
    each corpus in turn, it starts the service, ingests unless the cache
    matches, and answers. It grades, then writes the trace and the record.

    A clean run with complete usage goes to ``benchmarks/results/``, and a full
    run uploads its trace first. Any other run goes to ``reports/benchmarks/``.

    Args:
        name: The domain name.
        domain: The dataset adapter and grader.
        mode: ``lite`` or ``full``.
        options: The limits of this run.
        env: The environment, with every part a test can replace.

    Returns:
        The record and the path it was written to.

    Raises:
        RunRefusedError: The run cannot start or the owner declined it.
        SpendCapError: The estimate is above the cap, or no cap exists.
        InfrastructureError: A provider or network error survived the retries.
    """
    if mode == "full" and env.trace_repo is None:
        raise RunRefusedError("a full run needs BENCH_TRACE_REPO for its trace")
    plan = make_plan(name, domain, mode, options, chunking=env.chunking, cost=env.cost)
    manifest, documents, bound, cap = (
        plan.manifest,
        plan.documents,
        plan.bound,
        plan.cap,
    )
    if mode == "full" and not options.yes and not env.confirm(bound):
        raise RunRefusedError("full run declined")

    now = datetime.now(UTC)
    run_id = f"{now:%Y%m%dT%H%M%SZ}-{name}-{mode}-{env.system_name}-{uuid4().hex[:6]}"
    work_dir = env.reports_dir / mode / run_id
    trace_path = work_dir / TRACE_NAME
    tracing = start_tracing(trace_path)
    ctx = _Context(options, env, tracing)
    started = time.monotonic()
    try:
        corpora, schemas, outcomes = await _execute(
            manifest, domain, documents, bound, ctx
        )
        judge = env.make_judge(tracing.tracer)
        questions = await _bounded(
            options.concurrency,
            outcomes,
            lambda o: _grade(o, domain.grader_for(mode), judge, ctx),
        )
    finally:
        tracing.close()
    wall = time.monotonic() - started

    summary = summarize(tracing.memory.get_finished_spans())
    for question in questions:
        spans = summary.by_question.get(question.id)
        if spans:
            question.llm_calls = spans.llm_calls
            question.retrieved_chunk_ids = spans.retrieved_chunk_ids
    agent = env.agent_config
    record = RunRecord(
        run_id=run_id,
        created_at=now.isoformat(timespec="seconds"),
        domain=name,
        mode=mode,
        system=env.system_name,
        code=env.code,
        dataset=DatasetInfo(
            name=manifest.name,
            upstream=manifest.upstream,
            manifest_sha256=manifest.manifest_sha256(),
            question_ids_sha256=manifest.question_ids_sha256(),
            n_questions=len(manifest.questions),
        ),
        schemas=schemas,
        chunking=ChunkingInfo(
            fingerprint=env.chunking.fingerprint,
            settings=env.chunking.settings(),
        ),
        models=env.models,
        config=RunConfig(
            sha256=canonical_sha256(
                {
                    "agent": agent,
                    "concurrency": options.concurrency,
                    "seed": options.seed,
                }
            ),
            agent=agent,
            concurrency=options.concurrency,
            question_timeout_s=options.question_timeout_s,
            seed=options.seed,
        ),
        corpora=corpora,
        usage=UsageRecord(
            llm_calls=summary.total.llm_calls,
            input_tokens=summary.total.input_tokens,
            output_tokens=summary.total.output_tokens,
            by_path=summary.by_path,
            spend_cap=cap,
            usage_complete=summary.usage_complete,
            wall_seconds=wall,
        ),
        scores=aggregate(questions),
        questions=questions,
    )
    directory = run_directory(record, results=env.results_dir, reports=env.reports_dir)
    if record.lands_in_results and mode == "full":
        assert env.trace_repo is not None
        record.trace = env.upload(trace_path, repo=env.trace_repo, run_id=run_id)
        path = write_record(record, directory, results=env.results_dir)
    else:
        path = write_record(
            record, directory, trace=trace_path, results=env.results_dir
        )
    return record, path
