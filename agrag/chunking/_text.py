"""Shared helpers that build text Chunks from character spans."""

import bisect
from array import array
from collections.abc import Callable, Iterable, Sequence
from uuid import UUID

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, HeadingRef
from agrag.common.data_models.provenance import TextProvenance


def _line_start_offsets(text: str) -> array:
    """Return the character offset where each line begins in normalized text.

    Uses a compact ``array`` of 64-bit ints rather than a list of Python ints,
    since a large, densely-lined document otherwise holds one boxed int
    object per line just to support the bisect lookup below.

    Args:
        text: The document text, with LF line endings.

    Returns:
        The offsets, in document order. The first entry is always ``0``.
    """
    offsets = array("q", (0,))
    offsets.extend(index + 1 for index, char in enumerate(text) if char == "\n")
    return offsets


def _line_for_offset(line_starts: array, char_offset: int) -> int:
    """Return the 1-based line number at char_offset, given precomputed line starts.

    Args:
        line_starts: The character offsets where each line begins, from
            ``_line_start_offsets``.
        char_offset: The character offset to locate.

    Returns:
        The line number that contains the offset.
    """
    return bisect.bisect_right(line_starts, char_offset)


def _heading_path_for(char_start: int, outline: list[HeadingRef]) -> list[str]:
    """Return the heading path that contains char_start, outermost first.

    Args:
        char_start: The character offset of a chunk in the document text.
        outline: The document's heading outline, in document order.

    Returns:
        The texts of the headings active at char_start, from outermost to innermost.
    """
    active: dict[int, str] = {}
    for heading in outline:
        if heading.char_start > char_start:
            break
        for level in [level for level in active if level >= heading.level]:
            del active[level]
        active[heading.level] = heading.text
    return [active[level] for level in sorted(active)]


def build_text_chunks(
    document: Document,
    spans: Iterable[tuple[int, int]],
    *,
    level: int = 0,
    parent_ids: Sequence[UUID | None] | None = None,
) -> list[Chunk]:
    """Build text chunks from character spans of a document.

    The chunk text is the slice of ``document.text`` at each span. This function
    computes ``line_start`` and ``line_end`` from the span and sets ``heading_path``
    from the document's heading outline.

    Args:
        document: The document the spans index. This function reads its ``text``,
            ``heading_outline`` and identity fields.
        spans: Half-open character spans, in chunk order.
        level: The level to set on every chunk. A parent chunk has level 1.
        parent_ids: The parent chunk id of each span, in the order of ``spans``.
            ``None`` sets no parent on any chunk.

    Returns:
        The chunks, in the order of the spans.
    """
    document_id = Document.node_id_for(document_key=document.resolved_document_key)
    version_id = Document.id_for(content_hash=document.content_hash)
    line_starts = _line_start_offsets(document.text)
    chunks: list[Chunk] = []
    for index, (char_start, char_end) in enumerate(spans):
        parent_id = parent_ids[index] if parent_ids is not None else None
        provenance = TextProvenance(
            char_start=char_start,
            char_end=char_end,
            line_start=_line_for_offset(line_starts, char_start),
            line_end=_line_for_offset(line_starts, char_end),
        )
        chunks.append(
            Chunk(
                id=Chunk.id_for(
                    document_id=document_id,
                    version_id=version_id,
                    provenance=provenance,
                    index=index,
                    level=level,
                ),
                document_id=document_id,
                index=index,
                text=document.text[char_start:char_end],
                provenance=provenance,
                level=level,
                parent_id=parent_id,
                heading_path=_heading_path_for(char_start, document.heading_outline),
                content_kind="text",
            )
        )
    return chunks


def build_marked_chunks(
    document: Document, pieces: Iterable[tuple[int, int, str | None]]
) -> list[Chunk]:
    """Build text chunks from spans that can name the chunker that made them.

    Args:
        document: The document the spans index.
        pieces: ``(char_start, char_end, chunker)`` per chunk, in chunk order. A
            chunker of ``None`` leaves ``Chunk.chunker`` for the caller to fill.

    Returns:
        The chunks, in the order of the pieces.
    """
    pieces = list(pieces)
    chunks = build_text_chunks(document, [(start, end) for start, end, _ in pieces])
    return [
        chunk if name is None else chunk.model_copy(update={"chunker": name})
        for chunk, (_, _, name) in zip(chunks, pieces, strict=True)
    ]


def shifted_spans(
    spans_of: Callable[[str], list[tuple[int, int]]], text: str, start: int, end: int
) -> list[tuple[int, int]]:
    """Cut ``text[start:end]`` with ``spans_of`` and return spans in ``text`` offsets.

    Args:
        spans_of: A function from text to half-open spans, for example
            ``SpanChunker.spans``.
        text: The whole document text.
        start: The start of the slice to cut.
        end: The end of the slice to cut.

    Returns:
        The spans of the slice, shifted by ``start``.
    """
    return [(a + start, b + start) for a, b in spans_of(text[start:end])]
