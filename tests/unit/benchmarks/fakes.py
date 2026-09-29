"""A fake domain, system, graph store and compose runner for harness tests.

The fake system emits OpenInference LLM spans with token counts, so the harness
reads its usage the way it reads a real run. Nothing here calls a model, Docker
or Neo4j.
"""

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from opentelemetry.trace import Tracer

from agrag.common.data_models.document import Document
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from benchmarks.datasets.base import DatasetAdapter, Domain, text_document
from benchmarks.grading.base import Grade, Grader
from benchmarks.harness.config import BENCH_CHUNKING, CostModel
from benchmarks.harness.record import CodeIdentity
from benchmarks.harness.runner import RunEnvironment, SystemContext
from benchmarks.harness.services import SERVICE_PORTS, Services
from benchmarks.models import (
    BenchmarkQuestion,
    Corpus,
    CorpusDocument,
    CorpusManifest,
)
from benchmarks.systems.base import AgentFailureError, SystemAnswer


SCHEMA = GraphSchema(
    name="fake",
    version="1",
    entities=[EntityType(label="Thing", description="Any thing.")],
    relations=[],
)
COST = CostModel(
    calls_per_chunk=2,
    tokens_per_chunk=100,
    agent_calls_per_question=5,
    agent_tokens_per_question=500,
    judge_tokens_per_call=200,
)
LLM = {"openinference.span.kind": "LLM"}


def llm_span(
    tracer: Tracer, *, prompt: int | None = 10, completion: int | None = 5
) -> None:
    """Emit one finished LLM span with token counts."""
    attributes: dict[str, Any] = {**LLM}
    if completion is not None:
        attributes["llm.token_count.completion"] = completion
    if prompt is not None:
        attributes["llm.token_count.prompt"] = prompt
    with tracer.start_as_current_span("llm", attributes=attributes):
        pass


class FakeStore:
    """A stand-in for the graph store of one service.

    The marker lives in ``volume``, which survives a stop and is cleared by
    ``down``, as a compose volume is.
    """

    def __init__(self, volume: dict[str, Any]) -> None:
        """Share ``volume`` with every store opened on the same service."""
        self.volume = volume
        self.closed = False

    async def connect(self) -> None:
        """Do nothing."""

    async def close(self) -> None:
        """Record the close."""
        self.closed = True

    async def execute_read(self, query: str, parameters=None) -> list[dict]:
        """Answer the harness's marker and count queries."""
        if "BenchmarkMarker" in query:
            return [self.volume["marker"]] if "marker" in self.volume else []
        if "labels(n)" in query:
            return [{"label": "Thing", "count": 3}]
        return []

    async def execute_write(self, query: str, parameters=None) -> list[dict]:
        """Keep the marker the harness writes."""
        stored = parameters or {}
        self.volume["marker"] = {"key": stored["key"], "usage": stored["usage"]}
        return []


class FakeSystem:
    """A system that emits spans and returns canned answers."""

    name = "fake"

    def __init__(self, context: SystemContext, behaviour: "Behaviour") -> None:
        """Serve one corpus and report to ``behaviour``."""
        self.context = context
        self.behaviour = behaviour

    async def ingest(self) -> None:
        """Emit two extraction calls and one resolution call per document."""
        self.behaviour.ingests.append(self.context.corpus.id)
        for _ in self.context.documents:
            with self.context.tracer.start_as_current_span(
                "agrag.extraction.extract_chunk"
            ):
                llm_span(self.context.tracer, prompt=100, completion=10)
                llm_span(self.context.tracer, prompt=100, completion=10)
            llm_span(self.context.tracer, prompt=7, completion=3)

    async def answer(self, question: BenchmarkQuestion) -> SystemAnswer:
        """Return a canned answer, or fail as the behaviour says."""
        self.behaviour.asked.append(question)
        self.behaviour.attempts += 1
        if question.id in self.behaviour.agent_failures:
            raise AgentFailureError("recursion limit")
        if question.id in self.behaviour.slow:
            await asyncio.sleep(5)
        if self.behaviour.infra_error is not None:
            raise self.behaviour.infra_error
        llm_span(self.context.tracer, prompt=20, completion=8)
        return SystemAnswer(text=f"answer to {question.query}")

    async def teardown(self) -> None:
        """Close the store."""
        await self.context.store.close()


class Behaviour:
    """What the fake system does, and what it saw."""

    def __init__(self) -> None:
        """Start with no failures and nothing seen."""
        self.agent_failures: set[str] = set()
        self.slow: set[str] = set()
        self.infra_error: Exception | None = None
        self.asked: list[BenchmarkQuestion] = []
        self.ingests: list[str] = []
        self.attempts = 0


class FakeGrader(Grader):
    """Scores every answer 1.0 and makes one judge span.

    The fake judge is the run's tracer, so the grader can emit its span.
    """

    metrics = ("correctness",)
    judge_calls_per_question = 1

    async def grade(self, question, answer, judge) -> Grade:
        """Return a full score and the flag the fixture asks for."""
        llm_span(judge, prompt=30, completion=2)
        return Grade({"correctness": 1.0}, flags=question.reference.get("flags", []))


class FakeAdapter(DatasetAdapter):
    """Two corpora with two questions each; one question is multi-turn."""

    def load(self, mode: str) -> CorpusManifest:
        """Build the fake manifest."""
        corpora = [
            Corpus(
                id=f"c{i}",
                service="fake" if i == 1 else "fake2",
                schema_name="fake",
                documents=[
                    CorpusDocument(id="d", uri=f"c{i}/d.txt", sha256="0", source="x")
                ],
            )
            for i in (1, 2)
        ]
        questions = [
            BenchmarkQuestion(
                id=f"q{i}{j}",
                corpus_id=f"c{i}",
                messages=[{"role": "user", "content": f"question {i}{j}"}],
                group="g1" if j == 1 else "g2",
            )
            for i in (1, 2)
            for j in (1, 2)
        ]
        questions[1] = questions[1].model_copy(
            update={
                "messages": [
                    {"role": "user", "content": "first"},
                    {"role": "assistant", "content": "reply"},
                    {"role": "user", "content": "second"},
                ]
            }
        )
        return CorpusManifest(
            name="fake",
            domain="fake",
            mode=mode,
            upstream={"revision": "r"},
            corpora=corpora,
            questions=questions,
        )

    def documents(self, corpus: Corpus) -> Sequence[Document]:
        """Return one short document."""
        return [text_document("Some text. " * 40, uri=corpus.documents[0].uri)]

    def schema(self, corpus: Corpus) -> GraphSchema:
        """Return the fake schema."""
        return SCHEMA


DOMAIN = Domain(adapter=FakeAdapter(), grader=FakeGrader())


class Commands:
    """Records the docker commands and clears a service's volume on ``down``."""

    def __init__(self) -> None:
        """Start with no calls and no volumes."""
        self.calls: list[list[str]] = []
        self.volumes: dict[str, dict[str, Any]] = {}

    def __call__(self, command: Sequence[str]) -> None:
        """Record a command, and drop the volume when it is ``down``."""
        self.calls.append(list(command))
        if command[4] == "down":
            self.volumes.pop(command[-1], None)

    def verbs(self) -> list[str]:
        """Return the compose verb of each call, such as ``up`` or ``down``."""
        return [call[4] for call in self.calls]


def make_code(*, dirty: bool = False, tree: str = "tree1") -> CodeIdentity:
    """Build a code identity."""
    return CodeIdentity(
        agrag_version="0.0.2",
        git_describe="v0.0.2-1-gabc",
        git_commit="abc",
        git_dirty=dirty,
        agrag_tree=tree,
        benchmarks_code_sha256="b",
        uv_lock_sha256="l",
    )


def make_environment(
    tmp_path: Path, behaviour: Behaviour, **overrides: Any
) -> tuple[RunEnvironment, Commands]:
    """Build an environment whose parts are all fakes.

    The services ``fake`` and ``fake2`` must be in ``SERVICE_PORTS``.
    """
    commands = Commands()

    def open_store(settings, tracer) -> FakeStore:
        service = next(
            n for n, port in SERVICE_PORTS.items() if str(port) in settings.uri
        )
        return FakeStore(commands.volumes.setdefault(service, {}))

    async def no_sleep(_seconds: float) -> None:
        return None

    values: dict[str, Any] = {
        "system_name": "fake",
        "code": make_code(),
        "chunking": BENCH_CHUNKING,
        "models": {
            "agent": {"model_id": "m1"},
            "judge": {"model_id": "m1"},
            "extractor": {"model_id": "m1"},
            "embedder": {"model": "e"},
        },
        "agent_config": {"recursion_limit": 50},
        "make_system": lambda context: FakeSystem(context, behaviour),
        "make_judge": lambda tracer: tracer,
        "services": Services(runner=commands),
        "open_store": open_store,
        "cost": COST,
        "sleep": no_sleep,
        "results_dir": tmp_path / "results",
        "reports_dir": tmp_path / "reports",
        "embedder_model": "e",
    }
    values.update(overrides)
    return RunEnvironment(**values), commands
