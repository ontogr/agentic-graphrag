"""Helpers shared by discovery, fetch and citation checks."""

from collections.abc import Iterable, Mapping
from typing import Any

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document
from agrag.common.data_models.evidence import (
    CONTENT_HASH_PREFIX_LENGTH,
    EvidenceKind,
    EvidenceReference,
)
from agrag.common.data_models.provenance import TextProvenance


def scope_node_ids(scope: Iterable[str]) -> frozenset[str]:
    """Return the Document node id string of each document key in scope.

    Args:
        scope: Document keys.

    Returns:
        The node ids as lowercase UUID strings, matching ``Chunk.document_id``.
    """
    return frozenset(str(Document.node_id_for(document_key=key)) for key in scope)


def chunk_from_row(properties: Mapping[str, Any]) -> Chunk:
    """Build a Chunk from the properties of a stored Chunk node.

    Null properties are dropped, because the writer omits empty optional fields.

    Args:
        properties: The node properties, including the ``id`` property.

    Returns:
        The validated chunk.
    """
    data = {key: value for key, value in properties.items() if value is not None}
    return Chunk.from_node(data)


def text_range(chunk: Chunk) -> tuple[int, int] | None:
    """Return the document text offsets of a chunk, or None without text offsets.

    Args:
        chunk: The chunk.

    Returns:
        ``(char_start, char_end)`` for text provenance, else None.
    """
    if isinstance(chunk.provenance, TextProvenance):
        return chunk.provenance.char_start, chunk.provenance.char_end
    return None


def chunk_reference(chunk: Chunk) -> EvidenceReference:
    """Return the reference a discovery hit uses for a chunk.

    A chunk with text offsets gives a span over its own range. Any other chunk gives
    a chunk reference. Both forms name the same passage whichever search leg found
    it, so the hit has one evidence id.

    Args:
        chunk: The chunk.

    Returns:
        A span reference for text provenance with a non-empty range, else a chunk
        reference.
    """
    prefix = chunk.content_hash[:CONTENT_HASH_PREFIX_LENGTH]
    bounds = text_range(chunk)
    if bounds is not None and bounds[0] < bounds[1]:
        return EvidenceReference(
            kind=EvidenceKind.SPAN,
            document_node_id=chunk.document_id,
            content_hash_prefix=prefix,
            char_start=bounds[0],
            char_end=bounds[1],
        )
    return EvidenceReference(
        kind=EvidenceKind.CHUNK,
        document_node_id=chunk.document_id,
        content_hash_prefix=prefix,
        chunk_id=chunk.id,
    )
