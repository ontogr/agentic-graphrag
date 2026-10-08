"""Tests for the PDF loader with the real docling models.

The first run downloads the layout and table models, which takes a few minutes and
needs the network.
"""

import io
from pathlib import Path

import pytest

from agrag.chunking import Chunker
from agrag.common.data_models.document import Document, UnitKind
from agrag.loaders.corpus.types import ReadOptions, SourceRef
from agrag.loaders.docling.loader import DoclingPdfLoader


pytest.importorskip("docling_ibm_models")

BOOKMARKED = Path(__file__).parent / "fixtures" / "bookmarked.pdf"


def _load(path: Path) -> Document:
    source = SourceRef(uri=path.name, extension=path.suffix)
    stream = io.BytesIO(path.read_bytes())
    return next(iter(DoclingPdfLoader().load(source, stream, ReadOptions())))


class TestChunksFromAPdf:
    """The chunker keeps the page boxes of a PDF."""

    def test_every_chunk_has_a_page_span(self) -> None:
        """A PDF chunk can be shown on its page."""
        chunks = Chunker().chunk(_load(BOOKMARKED))

        assert chunks
        assert all(chunk.provenance.page_spans for chunk in chunks)


class TestBookmarkedPdf:
    """A PDF with bookmarks gets its heading depth from them."""

    def test_headings_take_the_depth_of_their_bookmarks(self) -> None:
        """Seven of eight headings match a bookmark. The eighth stays at depth 1."""
        document = _load(BOOKMARKED)

        outline = [(s.depth, s.heading) for s in document.sections if s.heading]
        assert outline[:3] == [
            (1, "Quarterly Operations Report"),
            (2, "Background"),
            (2, "Scope of Work"),
        ]
        assert (3, "Regional Revenue") in outline
        assert (1, "Fake Bold Heading") in outline

    def test_content_keeps_its_page_and_box(self) -> None:
        """Every unit of a PDF has at least one page span."""
        document = _load(BOOKMARKED)

        units = [u for s in document.sections for u in s.units]
        assert units
        assert all(u.pages for u in units)

    def test_a_table_has_rows(self) -> None:
        """The fixture holds one table."""
        document = _load(BOOKMARKED)

        tables = [
            u for s in document.sections for u in s.units if u.kind == UnitKind.TABLE
        ]
        assert len(tables) == 1
        assert len(tables[0].rows) > 1
