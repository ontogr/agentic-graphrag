"""Span helpers shared by the retrieval spans.

Every retrieval span that returns a list records the results the same way, so a
trace answers "what came back" without a second lookup.
"""

import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from openinference.semconv.trace import (
    DocumentAttributes,
    OpenInferenceMimeTypeValues,
    OpenInferenceSpanKindValues,
    SpanAttributes,
)
from opentelemetry.trace import Span, Tracer

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.community import Community
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.query_value import QueryValue
from agrag.common.data_models.relation import Relation
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.search_result import SearchResult
from agrag.observability import get_tracer
from agrag.retrieval.filters import SearchFilters


MAX_DOCUMENT_ATTRIBUTES = 20


def result_text(result: SearchResult) -> str:
    """Return the text a result stands for.

    Entities, resolved entities and communities give their embedding text,
    chunks their text, relations ``TYPE(source_id, target_id)``, and scalar
    query rows JSON.

    Args:
        result: The result to render.

    Returns:
        The text the result's item stands for.
    """
    item: Any = result.item
    if isinstance(item, (Entity, ResolvedEntity, Community)):
        return item.embedding_text
    if isinstance(item, Chunk):
        return item.text
    if isinstance(item, Relation):
        return f"{item.type}({item.source_id}, {item.target_id})"
    if isinstance(item, QueryValue):
        return json.dumps(item.value, default=str)
    return str(item)


def filters_json(filters: SearchFilters | None) -> str:
    """Return the scope as JSON, an empty scope when ``filters`` is None.

    Args:
        filters: The scope a search or retriever ran with, or None.

    Returns:
        The scope as JSON, never None, so a span always records it.
    """
    return (filters or SearchFilters()).model_dump_json()


def record_results(span: Span, results: Sequence[SearchResult]) -> None:
    """Write the results onto ``span``.

    Full lists go in array attributes, one attribute per array, so the SDK's
    per-span attribute limit does not cut a long list. The first
    ``MAX_DOCUMENT_ATTRIBUTES`` results also use the OpenInference
    ``retrieval.documents.N.*`` names, which viewers draw as a retrieval panel.

    Args:
        span: The span that returned ``results``. No-op when it is not
            recording.
        results: The results the span's wrapped call returned, in order.
    """
    if not span.is_recording():
        return
    span.set_attribute("agrag.result_count", len(results))
    if not results:
        return
    ids = [str(result.item.id) for result in results]
    kinds = [type(result.item).__name__ for result in results]
    texts = [result_text(result) for result in results]
    span.set_attribute("agrag.result_ids", ids)
    span.set_attribute("agrag.result_scores", [result.score for result in results])
    span.set_attribute("agrag.result_kinds", kinds)
    span.set_attribute("agrag.result_texts", texts)
    for index, result in enumerate(results[:MAX_DOCUMENT_ATTRIBUTES]):
        prefix = f"{SpanAttributes.RETRIEVAL_DOCUMENTS}.{index}"
        span.set_attribute(f"{prefix}.{DocumentAttributes.DOCUMENT_ID}", ids[index])
        span.set_attribute(
            f"{prefix}.{DocumentAttributes.DOCUMENT_CONTENT}", texts[index]
        )
        span.set_attribute(
            f"{prefix}.{DocumentAttributes.DOCUMENT_SCORE}", result.score
        )
        span.set_attribute(
            f"{prefix}.{DocumentAttributes.DOCUMENT_METADATA}",
            json.dumps({"kind": kinds[index], "method": result.method}),
        )


@contextmanager
def retrieval_span(
    tracer: Tracer | None,
    name: str,
    *,
    query: str,
    filters: SearchFilters | None,
    attributes: dict[str, Any] | None = None,
) -> Iterator[Span]:
    """Open a ``RETRIEVER`` span that records the query and the scope.

    Use it for retriever spans and for root spans that return
    ``SearchResult``s. The caller calls ``record_results`` on the yielded span
    before it exits.

    Args:
        tracer: The caller's tracer, or None for a no-op tracer.
        name: The span name, in the ``agrag.retrieval.*`` namespace.
        query: The natural-language query, or the seed's text.
        filters: The scope the wrapped call runs under, always recorded.
        attributes: Extra cheap attributes known before the call starts.

    Yields:
        The open span, for ``record_results`` and any later attributes.
    """
    with get_tracer(tracer).start_as_current_span(name) as span:
        if span.is_recording():
            span.set_attributes(
                {
                    SpanAttributes.OPENINFERENCE_SPAN_KIND: (
                        OpenInferenceSpanKindValues.RETRIEVER.value
                    ),
                    SpanAttributes.INPUT_VALUE: query,
                    SpanAttributes.INPUT_MIME_TYPE: (
                        OpenInferenceMimeTypeValues.TEXT.value
                    ),
                    "agrag.query": query,
                    "agrag.filters": filters_json(filters),
                    **(attributes or {}),
                }
            )
        yield span
