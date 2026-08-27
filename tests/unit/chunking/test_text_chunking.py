"""Tests for the text chunker and default chunker builder."""

from agrag.chunking import default_chunker
from agrag.chunking.text import chunk_document
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat


def _document(text: str, outline=None) -> Document:
    return Document(
        text=text,
        title="t",
        uri="u",
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash="h",
        loader_name="text",
        char_count=len(text),
        line_count=text.count("\n") + 1,
        heading_outline=outline or [],
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
            assert chunk.document_id == doc.id
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
