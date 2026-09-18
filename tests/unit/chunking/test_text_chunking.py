"""Tests for chunk_document and default_chunker in agrag.chunking.

Verifies character-span and line-number provenance on produced chunks, index
ordering, heading-path tracking from a document's heading outline, and the
character-based recursive default chunker's size limit. One test calls the
private ``_heading_path_for`` helper directly to isolate a stale-heading bug
from chonkie's tokenizer-dependent chunk boundaries.
"""

from agrag.chunking import default_chunker
from agrag.chunking.text import chunk_document
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat


def _document(
    text: str,
    outline=None,
    content_hash: str = "h",
    record_id: str | None = None,
) -> Document:
    return Document(
        text=text,
        title="t",
        uri="u",
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=content_hash,
        loader_name="text",
        char_count=len(text),
        line_count=text.count("\n") + 1,
        heading_outline=outline or [],
        record_id=record_id,
    )


class TestChunkDocument:
    """Verify character spans, line numbers, and heading paths."""

    def test_splits_into_chunks_with_text_provenance(self) -> None:
        """Splits into chunks with text provenance."""
        doc = _document("word " * 200)
        chunks = chunk_document(doc, default_chunker(chunk_size=64))
        assert len(chunks) > 1
        assert all(isinstance(c, Chunk) for c in chunks)
        for chunk in chunks:
            assert chunk.document_id == Document.node_id_for(
                document_key=doc.resolved_document_key
            )
            assert chunk.provenance.kind == "text"
            assert (
                chunk.text
                == doc.text[chunk.provenance.char_start : chunk.provenance.char_end]
            )

    def test_index_increases_in_order(self) -> None:
        """Index increases in order."""
        doc = _document("word " * 200)
        chunks = chunk_document(doc, default_chunker(chunk_size=64))
        assert [c.index for c in chunks] == list(range(len(chunks)))

    def test_content_versions_use_distinct_chunk_ids(self) -> None:
        """Chunks retain history when a document version uses the same span."""
        first = _document("first", content_hash="first", record_id="document")
        second = _document("other", content_hash="other", record_id="document")
        chunker = default_chunker(chunk_size=1024)

        first_chunk = chunk_document(first, chunker)[0]
        second_chunk = chunk_document(second, chunker)[0]

        assert first_chunk.document_id == second_chunk.document_id
        assert first.resolved_id == second.resolved_id
        assert first_chunk.provenance.char_start == second_chunk.provenance.char_start
        assert first_chunk.id != second_chunk.id

    def test_line_numbers_derived_from_char_span(self) -> None:
        """Line numbers derived from char span."""
        text = "line one\nline two\nline three"
        doc = _document(text)
        chunks = chunk_document(doc, default_chunker(chunk_size=1024))
        chunk = chunks[0]
        assert chunk.provenance.line_start == 1
        assert chunk.provenance.line_end == 3

    def test_heading_path_tracks_active_headings(self) -> None:
        """Heading path tracks active headings."""
        from agrag.common.data_models.document import HeadingRef  # noqa: PLC0415

        text = "# Title\n\nintro\n\n## Section\n\nbody\n"
        outline = [
            HeadingRef(text="Title", level=1, char_start=0),
            HeadingRef(text="Section", level=2, char_start=text.index("## Section")),
        ]
        doc = _document(text, outline=outline)
        chunks = chunk_document(doc, default_chunker(chunk_size=1024))
        body_chunk = [c for c in chunks if "body" in c.text][0]
        assert "Title" in body_chunk.heading_path

    def test_heading_path_drops_stale_deeper_heading(self) -> None:
        """A shallower heading clears any deeper heading still active from before.

        This exercises the private ``_heading_path_for`` helper directly. Routing
        it through the real chunker would couple the test to exactly where
        chonkie's tokenizer places chunk boundaries, which has nothing to do with
        this outline-tracking bug.
        """
        from agrag.chunking.text import _heading_path_for  # noqa: PLC0415
        from agrag.common.data_models.document import HeadingRef  # noqa: PLC0415

        outline = [
            HeadingRef(text="Title", level=1, char_start=0),
            HeadingRef(text="Section One", level=2, char_start=10),
            HeadingRef(text="Detail", level=3, char_start=20),
            HeadingRef(text="Section Two", level=2, char_start=30),
        ]
        assert _heading_path_for(35, outline) == ["Title", "Section Two"]


class TestDefaultChunker:
    """The default chunker is character-based and recursive."""

    def test_respects_chunk_size(self) -> None:
        """Respects chunk size."""
        chunker = default_chunker(chunk_size=32)
        doc = _document("word " * 100)
        chunks = chunk_document(doc, chunker)
        assert all(len(c.text) <= 64 for c in chunks)
