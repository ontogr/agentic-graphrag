"""Usage counting from OpenTelemetry spans.

The harness installs one in-memory exporter around a whole run. Calls and tokens
come only from spans of the OpenInference ``LLM`` kind; parent spans carry no
tokens, so nothing counts twice. A BAML span is one provider request. An agent or
judge span is one LangChain call and can cover several HTTP requests, so agent
and judge call counts are a lower bound.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry.sdk.trace import ReadableSpan, SpanLimits, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import Tracer

from benchmarks.harness.record import PathUsage
from benchmarks.harness.trace import GzipJsonlSpanExporter


INGEST_SPAN = "benchmark.ingest"
QUESTION_SPAN = "benchmark.question"
GRADE_SPAN = "benchmark.grade"
CORPUS_ATTRIBUTE = "benchmark.corpus_id"
QUESTION_ATTRIBUTE = "benchmark.question_id"

# The default of 128 drops attributes silently on long agent runs.
_MAX_ATTRIBUTES = 100_000

_SEARCH_SPAN = "agrag.retrieval.search"
_EXTRACTION_PREFIX = "agrag.extraction."
_EXTRACTION_BAML_SPAN = "agrag.extraction.baml"
_JUDGE_SPANS = ("agrag.eval.judge", GRADE_SPAN)
PATHS = ("agent", "extraction", "judge", "other")


@dataclass
class Tracing:
    """The provider, tracer and exporters for one run.

    Attributes:
        provider: The provider that feeds both exporters.
        tracer: A tracer to inject into every agrag component.
        memory: The exporter that holds finished spans for counting.
    """

    provider: TracerProvider
    tracer: Tracer
    memory: InMemorySpanExporter

    def close(self) -> None:
        """Flush and close the exporters, which finishes the trace file."""
        self.provider.shutdown()


def start_tracing(trace_path: Path) -> Tracing:
    """Build a provider that counts spans in memory and writes them to a file.

    Args:
        trace_path: Where the gzipped trace goes.
    """
    provider = TracerProvider(span_limits=SpanLimits(max_attributes=_MAX_ATTRIBUTES))
    memory = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    provider.add_span_processor(SimpleSpanProcessor(GzipJsonlSpanExporter(trace_path)))
    return Tracing(provider, provider.get_tracer("benchmarks"), memory)


@dataclass
class CorpusSpans:
    """Ingest usage and empty extractions for one corpus."""

    usage: PathUsage = field(default_factory=PathUsage)
    empty_extractions: int = 0


@dataclass
class QuestionSpans:
    """LLM calls and retrieved chunk ids for one question."""

    llm_calls: int = 0
    retrieved_chunk_ids: list[str] = field(default_factory=list)


@dataclass
class UsageSummary:
    """Usage read from a run's spans.

    Attributes:
        total: The sum over every LLM span.
        by_path: The sum per path: agent, extraction, judge and other. The other
            path holds resolution, merge and community calls.
        usage_complete: False when an LLM span has no prompt token count.
        by_corpus: Ingest usage and empty extractions per corpus id.
        by_question: Calls and retrieved chunk ids per question id.
    """

    total: PathUsage
    by_path: dict[str, PathUsage]
    usage_complete: bool
    by_corpus: dict[str, CorpusSpans]
    by_question: dict[str, QuestionSpans]


def _is_llm(span: ReadableSpan) -> bool:
    """Tell an LLM-kind span from any other."""
    kind = (span.attributes or {}).get(SpanAttributes.OPENINFERENCE_SPAN_KIND)
    return kind == OpenInferenceSpanKindValues.LLM.value


def _count(value: object) -> int:
    """Read a token count attribute, treating a missing one as zero."""
    return value if isinstance(value, int) else 0


def _strings(value: object) -> list[str]:
    """Read a string-array attribute, treating a missing one as empty."""
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return []


def _path_of(name: str) -> str | None:
    """Return the usage path a span name marks, or None."""
    if name.startswith(_EXTRACTION_PREFIX):
        return "extraction"
    if name in _JUDGE_SPANS:
        return "judge"
    if name == QUESTION_SPAN:
        return "agent"
    return None


def summarize(spans: Sequence[ReadableSpan]) -> UsageSummary:
    """Sum calls and tokens by path, corpus and question.

    A span belongs to the path of its nearest ancestor (or itself) that names one.
    Spans with no such ancestor, such as resolution, merge and community calls
    during ingest, go to ``other``.

    Args:
        spans: The finished spans of one run.
    """
    by_id = {span.context.span_id: span for span in spans}

    def ancestors(span: ReadableSpan):
        current: ReadableSpan | None = span
        while current is not None:
            yield current
            parent = current.parent
            current = by_id.get(parent.span_id) if parent else None

    total = PathUsage()
    by_path = {name: PathUsage() for name in PATHS}
    corpora: dict[str, CorpusSpans] = defaultdict(CorpusSpans)
    questions: dict[str, QuestionSpans] = defaultdict(QuestionSpans)
    complete = True

    for span in spans:
        attributes = span.attributes or {}
        chain = list(ancestors(span))
        corpus_id = next(
            (
                str(a.attributes[CORPUS_ATTRIBUTE])
                for a in chain
                if a.name == INGEST_SPAN and a.attributes
            ),
            None,
        )
        question_id = next(
            (
                str(a.attributes[QUESTION_ATTRIBUTE])
                for a in chain
                if a.name == QUESTION_SPAN and a.attributes
            ),
            None,
        )
        if (
            span.name == _EXTRACTION_BAML_SPAN
            and corpus_id is not None
            and attributes.get("agrag.entities_extracted") == 0
        ):
            corpora[corpus_id].empty_extractions += 1
        if span.name == _SEARCH_SPAN and question_id is not None:
            ids = _strings(attributes.get("agrag.result_ids"))
            kinds = _strings(attributes.get("agrag.result_kinds"))
            seen = questions[question_id].retrieved_chunk_ids
            for result_id, kind in zip(ids, kinds, strict=False):
                if kind == "Chunk" and str(result_id) not in seen:
                    seen.append(str(result_id))
        if not _is_llm(span):
            continue

        prompt = attributes.get(SpanAttributes.LLM_TOKEN_COUNT_PROMPT)
        completion = attributes.get(SpanAttributes.LLM_TOKEN_COUNT_COMPLETION)
        if prompt is None or completion is None:
            complete = False
        path = next((p for a in chain if (p := _path_of(a.name))), "other")
        for usage in (total, by_path[path]):
            usage.llm_calls += 1
            usage.input_tokens += _count(prompt)
            usage.output_tokens += _count(completion)
        if corpus_id is not None:
            corpus = corpora[corpus_id].usage
            corpus.llm_calls += 1
            corpus.input_tokens += _count(prompt)
            corpus.output_tokens += _count(completion)
        if question_id is not None:
            questions[question_id].llm_calls += 1

    return UsageSummary(total, by_path, complete, dict(corpora), dict(questions))
