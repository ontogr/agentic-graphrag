"""The run record: what a run committed to, pinned to the code that made it."""

import gzip
import hashlib
import json
import os
import shutil
import subprocess
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from benchmarks.models import Mode


REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "benchmarks" / "results"
REPORTS_DIR = REPO_ROOT / "reports" / "benchmarks"
TRACE_NAME = "trace.jsonl.gz"
RECORD_NAME = "record.json"
_FLOAT_PLACES = 4


class CodeIdentity(BaseModel):
    """The code that produced a run.

    ``agrag_version`` alone cannot identify a run because the version is static
    between releases. The tree hash of ``agrag/`` survives a squash merge.

    Attributes:
        agrag_version: The installed package version.
        git_describe: The output of ``git describe --tags --always``.
        git_commit: The commit hash.
        git_dirty: Whether tracked or untracked files differ from the commit,
            not counting ``benchmarks/results/``.
        agrag_tree: The tree hash of ``agrag/`` at the commit.
        benchmarks_code_sha256: A hash of the tracked files under ``benchmarks/``,
            not counting ``results/``.
        uv_lock_sha256: The hash of ``uv.lock``.
    """

    agrag_version: str
    git_describe: str
    git_commit: str
    git_dirty: bool
    agrag_tree: str
    benchmarks_code_sha256: str
    uv_lock_sha256: str


class DatasetInfo(BaseModel):
    """The dataset a run used, by hash."""

    name: str
    upstream: dict[str, Any] = Field(default_factory=dict)
    manifest_sha256: str
    question_ids_sha256: str
    n_questions: int


class SchemaInfo(BaseModel):
    """The graph schemas a run used. Each corpus can have its own."""

    name: str
    version: str
    sha256: str


class ChunkingInfo(BaseModel):
    """The chunking rules a run used and their fingerprint."""

    fingerprint: str
    settings: dict[str, Any]


class RunConfig(BaseModel):
    """The run settings that affect results."""

    sha256: str
    agent: dict[str, Any]
    judge_samples: int = 1
    concurrency: int
    question_timeout_s: float
    seed: int


class GraphStats(BaseModel):
    """Node and edge counts of an ingested graph, by schema type."""

    entities_by_label: dict[str, int] = Field(default_factory=dict)
    relations_by_type: dict[str, int] = Field(default_factory=dict)


class PathUsage(BaseModel):
    """Calls and tokens for one LLM path."""

    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class CorpusRecord(BaseModel):
    """What one corpus cost to ingest and what graph it produced.

    ``ingest_usage`` is the original cost, copied from the cache marker when
    ``ingest_cache_hit`` is true.
    """

    corpus_id: str
    service: str
    n_documents: int
    corpus_tokens: int | None = None
    chunks: int
    cache_key: str
    ingest_cache_hit: bool
    ingest_usage: PathUsage
    empty_extractions: int
    graph: GraphStats


class SpendCapRecord(BaseModel):
    """The spend cap a run was checked against."""

    llm_calls: int | None
    tokens: int | None
    overridden: bool


class UsageRecord(BaseModel):
    """Calls and tokens this run spent, from OpenTelemetry spans.

    Agent and judge call counts are a lower bound: LangChain and the provider
    SDKs retry below one span.
    """

    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    by_path: dict[str, PathUsage] = Field(default_factory=dict)
    spend_cap: SpendCapRecord
    usage_complete: bool = True
    wall_seconds: float = 0.0
    cost_usd: float | None = None


class MetricScore(BaseModel):
    """The mean of one metric and the number of questions behind it."""

    mean: float
    n: int


class Scores(BaseModel):
    """Aggregate scores and scores per group."""

    aggregate: dict[str, MetricScore] = Field(default_factory=dict)
    by_group: dict[str, dict[str, MetricScore]] = Field(default_factory=dict)


class QuestionRecord(BaseModel):
    """The outcome of one question: IDs and scores only, no text.

    Attributes:
        status: ``ok``, or ``agent_failure`` when the agent gave no usable answer.
            An infrastructure failure aborts the run and writes no record.
        flags: Domain facts, such as ``no_chunk_citation``.
        retrieved_chunk_ids: The chunk ids the searches returned, in order.
    """

    id: str
    corpus_id: str
    group: str
    status: Literal["ok", "agent_failure"]
    flags: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    llm_calls: int = 0
    latency_s: float = 0.0
    retrieved_chunk_ids: list[str] = Field(default_factory=list)


class TraceRef(BaseModel):
    """Where the trace is. ``repo`` and ``revision`` are set for a full run."""

    path: str
    sha256: str
    repo: str | None = None
    revision: str | None = None


class RunRecord(BaseModel):
    """The committed summary of one run."""

    schema_version: int = 1
    run_id: str
    created_at: str
    domain: str
    mode: Mode
    system: str
    code: CodeIdentity
    dataset: DatasetInfo
    schemas: list[SchemaInfo]
    chunking: ChunkingInfo
    models: dict[str, dict[str, Any]]
    config: RunConfig
    corpora: list[CorpusRecord]
    usage: UsageRecord
    scores: Scores
    questions: list[QuestionRecord]
    trace: TraceRef | None = None

    @property
    def lands_in_results(self) -> bool:
        """Whether a run may be committed under ``benchmarks/results/``."""
        return not self.code.git_dirty and self.usage.usage_complete


def sha256_file(path: Path) -> str:
    """Return the SHA-256 of a file's bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(root: Path, *args: str) -> str:
    """Run git in ``root`` and return stripped stdout."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def code_identity(root: Path = REPO_ROOT) -> CodeIdentity:
    """Read the identity of the code in ``root`` from git and the installed package.

    Args:
        root: The repository root.

    Returns:
        The code identity. ``benchmarks/results/`` is left out of the dirty check
        and of the code hash, so committing a run does not change either.
    """
    code_files = _git(
        root, "ls-files", "--", "benchmarks", ":!benchmarks/results"
    ).splitlines()
    code_hash = hashlib.sha256()
    for name in sorted(code_files):
        code_hash.update(name.encode())
        code_hash.update(bytes.fromhex(sha256_file(root / name)))
    dirty = _git(root, "status", "--porcelain", "--", ".", ":!benchmarks/results")
    return CodeIdentity(
        agrag_version=version("agentic-graphrag"),
        git_describe=_git(root, "describe", "--tags", "--always"),
        git_commit=_git(root, "rev-parse", "HEAD"),
        git_dirty=bool(dirty),
        agrag_tree=_git(root, "rev-parse", "HEAD:agrag"),
        benchmarks_code_sha256=code_hash.hexdigest(),
        uv_lock_sha256=sha256_file(root / "uv.lock"),
    )


def _round_floats(value: Any) -> Any:
    """Round every float in a JSON-like value so diffs between runs stay small."""
    if isinstance(value, float):
        return round(value, _FLOAT_PLACES)
    if isinstance(value, dict):
        return {key: _round_floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_round_floats(item) for item in value]
    return value


def run_directory(record: RunRecord, *, results: Path, reports: Path) -> Path:
    """Return the directory a run belongs in.

    A clean run with complete usage goes under ``results`` and is meant to be
    committed. Any other run goes under ``reports``, which git ignores.
    """
    base = results if record.lands_in_results else reports
    return base / record.mode / record.run_id


def write_record(
    record: RunRecord, directory: Path, *, trace: Path | None = None, results: Path
) -> Path:
    """Write a record, and its trace, into ``directory``.

    Args:
        record: The record to write. ``record.trace`` is set from ``trace`` unless
            the caller already set it, as a full run does after upload.
        directory: The run directory.
        trace: A gzipped trace to copy beside the record.
        results: The committed results root.

    Returns:
        The path of the written record.

    Raises:
        ValueError: ``directory`` is under ``results`` and the record is from a
            dirty tree or has incomplete usage.
    """
    if directory.is_relative_to(results) and not record.lands_in_results:
        raise ValueError(
            "a dirty or incomplete run cannot be written under benchmarks/results"
        )
    directory.mkdir(parents=True, exist_ok=True)
    if trace is not None:
        if trace.resolve() != (directory / TRACE_NAME).resolve():
            shutil.copyfile(trace, directory / TRACE_NAME)
        record.trace = TraceRef(path=TRACE_NAME, sha256=sha256_file(trace))
    payload = _round_floats(record.model_dump(mode="json"))
    path = directory / RECORD_NAME
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def read_trace(path: Path) -> list[dict[str, Any]]:
    """Read a gzipped trace into a list of OTLP JSON batches."""
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
