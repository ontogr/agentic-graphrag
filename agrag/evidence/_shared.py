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


def text_offsets(chunk: Chunk) -> tuple[int, int] | None:
    """Return the stored text offsets of a chunk, or None without text offsets.

    The offsets are the provenance as written. They do not show that the chunk
    text equals the document text at those offsets. Use ``text_range`` for that.

    Args:
        chunk: The chunk.

    Returns:
        ``(char_start, char_end)`` for text provenance, else None.
    """
    if isinstance(chunk.provenance, TextProvenance):
        return chunk.provenance.char_start, chunk.provenance.char_end
    return None


def text_range(chunk: Chunk) -> tuple[int, int] | None:
    """Return the offsets of a chunk whose text is exactly the range it names.

    A chunk under a heading holds the heading line in its text, but its offsets
    cover only the body. Such a chunk has no span: its text cannot be sliced from
    the document by those offsets. The lengths must match, because the document
    text is not stored and the length is the only check that needs no document.

    Args:
        chunk: The chunk.

    Returns:
        ``(char_start, char_end)`` when the chunk text length equals the range
        length, else None.
    """
    bounds = text_offsets(chunk)
    if bounds is None or bounds[1] - bounds[0] != len(chunk.text):
        return None
    return bounds


def chunk_reference(chunk: Chunk) -> EvidenceReference:
    """Return the reference a discovery hit uses for a chunk.

    A chunk whose text is exactly its text range gives a span over that range. Any
    other chunk, including a chunk under a heading, gives a chunk reference. Both
    forms name the same passage whichever search leg found it, so the hit has one
    evidence id.

    Args:
        chunk: The chunk.

    Returns:
        A span reference for a non-empty text range, else a chunk reference.
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
