"""Splits a text Document into Chunks with the chonkie chunker."""

import bisect
from array import array
from collections.abc import Iterator

from chonkie import RecursiveChunker

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, HeadingRef
from agrag.common.data_models.provenance import TextProvenance


def _line_start_offsets(text: str) -> array:
    """Return the character offset where each line begins in normalized text.

    Uses a compact ``array`` of 64-bit ints rather than a list of Python ints,
    since a large, densely-lined document would otherwise hold one boxed int
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


def chunk_document(document: Document, chunker: RecursiveChunker) -> list[Chunk]:
    """Split a document's text into chunks.

    This function computes ``line_start`` and ``line_end`` from each chunk's character
    span,
    because the chunker does not report line numbers. It also sets ``heading_path`` from
    the
    document's heading outline.

    Args:
        document: The document to split. This function reads only its ``text`` and
            ``heading_outline`` fields.
        chunker: The chunker to run.

    Returns:
        The chunks, in document order.
    """
    chunks: list[Chunk] = []
    line_starts = _line_start_offsets(document.text)
    for index, piece in enumerate(chunker.chunk(document.text)):
        char_start = piece.start_index
        char_end = piece.end_index
        provenance = TextProvenance(
            char_start=char_start,
            char_end=char_end,
            line_start=_line_for_offset(line_starts, char_start),
            line_end=_line_for_offset(line_starts, char_end),
        )
        chunks.append(
            Chunk(
                document_id=document.resolved_id,
                index=index,
                text=piece.text,
                provenance=provenance,
                heading_path=_heading_path_for(char_start, document.heading_outline),
                content_kind="text",
            )
        )
    return chunks


def iter_chunk_documents(
    documents: Iterator[Document], chunker: RecursiveChunker
) -> Iterator[Chunk]:
    """Chunk a stream of documents into a flat stream of chunks.

    Args:
        documents: The documents to chunk, in order.
        chunker: The chunker to run on each document.

    Yields:
        Each chunk, in document then chunk order.
    """
    for document in documents:
        yield from chunk_document(document, chunker)
