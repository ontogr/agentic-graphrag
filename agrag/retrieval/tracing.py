"""OpenTelemetry helpers for retrieval results."""

import json
from collections.abc import Sequence

from openinference.semconv.trace import DocumentAttributes, SpanAttributes
from opentelemetry.trace import Span

from agrag.common.data_models.chunk import Chunk


def record_chunks(span: Span, chunks: Sequence[Chunk]) -> None:
    """Record hydrated chunks as OpenTelemetry-safe attributes."""
    span.set_attribute("agrag.result.count", len(chunks))
    span.set_attribute(
        SpanAttributes.RETRIEVAL_DOCUMENTS,
        json.dumps(
            [
                {
                    DocumentAttributes.DOCUMENT_ID: str(chunk.id),
                    DocumentAttributes.DOCUMENT_CONTENT: chunk.text,
                    DocumentAttributes.DOCUMENT_METADATA: {
                        "document_id": str(chunk.document_id),
                        "level": chunk.level,
                    },
                }
                for chunk in chunks
            ]
        ),
    )
