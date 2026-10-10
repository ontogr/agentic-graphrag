"""Tests for the retrieval span helpers in agrag.retrieval.tracing.

Runs real spans through an in-memory OpenTelemetry exporter, so the attribute
names, array lengths and the OpenInference flattened document names are the
ones the SDK records. No store or network is involved.
"""

import json
from uuid import uuid4

from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.query_value import QueryValue
from agrag.common.data_models.relation import Relation
from agrag.common.data_models.search_result import SearchResult
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.tracing import (
    MAX_DOCUMENT_ATTRIBUTES,
    record_results,
    result_text,
    retrieval_span,
)


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Return a provider and exporter pair backed by one in-memory exporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _single_span(exporter: InMemorySpanExporter) -> ReadableSpan:
    """Return the only exported span, failing when there are more."""
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    return spans[0]


def _entity_result(score: float = 1.0) -> SearchResult:
    """Return one entity result."""
    return SearchResult(
        item=Entity(id=uuid4(), label="Person", name="Alice"),
        score=score,
        method="entity",
    )


def _chunk_result(score: float = 0.5) -> SearchResult:
    """Return one chunk result."""
    return SearchResult(
        item=Chunk(
            id=uuid4(),
            document_id=uuid4(),
            index=0,
            text="a passage of source text",
            provenance=TextProvenance(kind="text", char_start=0, char_end=0),
        ),
        score=score,
        method="chunk",
    )


def _relation_result() -> SearchResult:
    """Return one relation result."""
    return SearchResult(
        item=Relation(id=uuid4(), type="TREATS", source_id=uuid4(), target_id=uuid4()),
        score=1.0,
        method="bfs",
    )


def _query_value_result() -> SearchResult:
    """Return one scalar query-row result."""
    return SearchResult(item=QueryValue(value={"count": 3}), score=1.0, method="t2c")


class TestResultText:
    """result_text renders every item type."""

    def test_query_value_gives_json(self) -> None:
        """A scalar query row renders as JSON."""
        result = _query_value_result()
        assert result_text(result) == '{"count": 3}'


class TestRecordResults:
    """record_results writes full arrays and capped flattened documents."""

    async def test_zero_results_records_only_the_count(self) -> None:
        """An empty list records the count and nothing else."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        with retrieval_span(
            tracer, "agrag.retrieval.chunk", query="q", filters=None
        ) as span:
            record_results(span, [])

        attributes = _single_span(exporter).attributes
        assert attributes is not None
        assert attributes["agrag.result_count"] == 0
        assert "agrag.result_ids" not in attributes
        assert "agrag.result_texts" not in attributes
        assert not any(
            str(name).startswith("retrieval.documents.") for name in attributes
        )

    async def test_three_results_record_arrays_and_documents(self) -> None:
        """Three results fill the arrays and three flattened documents."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        results = [_entity_result(), _chunk_result(0.9), _relation_result()]
        with retrieval_span(
            tracer, "agrag.retrieval.chunk", query="q", filters=None
        ) as span:
            record_results(span, results)

        attributes = _single_span(exporter).attributes
        assert attributes is not None
        assert attributes["agrag.result_count"] == 3
        assert len(attributes["agrag.result_ids"]) == 3
        assert len(attributes["agrag.result_scores"]) == 3
        assert len(attributes["agrag.result_kinds"]) == 3
        assert len(attributes["agrag.result_texts"]) == 3
        assert list(attributes["agrag.result_ids"]) == [str(r.item.id) for r in results]
        assert list(attributes["agrag.result_scores"]) == [r.score for r in results]
        assert list(attributes["agrag.result_kinds"]) == [
            type(r.item).__name__ for r in results
        ]
        for index in range(3):
            prefix = f"retrieval.documents.{index}."
            assert attributes[f"{prefix}document.id"] == str(results[index].item.id)
            assert attributes[f"{prefix}document.content"] == result_text(
                results[index]
            )
            assert attributes[f"{prefix}document.score"] == results[index].score
            metadata = json.loads(attributes[f"{prefix}document.metadata"])
            assert metadata == {
                "kind": type(results[index].item).__name__,
                "method": results[index].method,
            }

    async def test_twenty_five_results_flatten_only_the_first_twenty(self) -> None:
        """25 results fill the arrays; flattened documents stop at 19."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        results = [_entity_result(float(index)) for index in range(25)]
        with retrieval_span(
            tracer, "agrag.retrieval.entity", query="q", filters=None
        ) as span:
            record_results(span, results)

        attributes = _single_span(exporter).attributes
        assert attributes is not None
        assert attributes["agrag.result_count"] == 25
        assert len(attributes["agrag.result_ids"]) == 25
        assert len(attributes["agrag.result_texts"]) == 25
        for index in range(MAX_DOCUMENT_ATTRIBUTES):
            assert f"retrieval.documents.{index}.document.id" in attributes
        assert (
            f"retrieval.documents.{MAX_DOCUMENT_ATTRIBUTES}.document.id"
            not in attributes
        )

    async def test_query_value_result_uses_its_own_id(self) -> None:
        """A QueryValue result records its own id and JSON text."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        result = _query_value_result()
        with retrieval_span(
            tracer, "agrag.retrieval.text2cypher", query="q", filters=None
        ) as span:
            record_results(span, [result])

        attributes = _single_span(exporter).attributes
        assert attributes is not None
        assert list(attributes["agrag.result_ids"]) == [str(result.item.id)]
        assert list(attributes["agrag.result_texts"]) == ['{"count": 3}']


class TestRetrievalSpan:
    """retrieval_span sets the RETRIEVER kind and the query attributes."""

    async def test_sets_kind_query_and_filters(self) -> None:
        """The span carries the kind, the input value and the JSON scope."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        filters = SearchFilters(labels=["Person"])
        with retrieval_span(
            tracer,
            "agrag.retrieval.chunk",
            query="who is alice",
            filters=filters,
            attributes={"agrag.limit": 5},
        ) as span:
            record_results(span, [])

        attributes = _single_span(exporter).attributes
        assert attributes is not None
        assert attributes["openinference.span.kind"] == "RETRIEVER"
        assert attributes["input.value"] == "who is alice"
        assert attributes["input.mime_type"] == "text/plain"
        assert attributes["agrag.query"] == "who is alice"
        assert json.loads(attributes["agrag.filters"]) == filters.model_dump()
        assert attributes["agrag.limit"] == 5

    async def test_none_filters_records_an_empty_scope(self) -> None:
        """None filters are recorded as the empty scope's JSON."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        with retrieval_span(
            tracer, "agrag.retrieval.chunk", query="q", filters=None
        ) as span:
            record_results(span, [])

        attributes = _single_span(exporter).attributes
        assert attributes is not None
        assert json.loads(attributes["agrag.filters"]) == SearchFilters().model_dump()
