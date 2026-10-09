"""Tests for the sections that the docling loader builds from real small files."""

import hashlib
import io
from pathlib import Path

import pytest

from agrag.common.data_models.document import Document, UnitKind
from agrag.loaders.corpus.types import ReadOptions, SourceRef
from agrag.loaders.docling.loader import DoclingLoader


pytest.importorskip("docling")

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str, uri: str | None = None, **options: object) -> Document:
    path = FIXTURES / name
    source = SourceRef(uri=uri or name, extension=Path(uri or name).suffix)
    stream = io.BytesIO(path.read_bytes())
    return next(iter(DoclingLoader().load(source, stream, ReadOptions(**options))))


def _outline(document: Document) -> list[tuple[int, str]]:
    return [(section.depth, section.heading) for section in document.sections]


class TestMarkdown:
    """Markdown headings become nested sections."""

    def test_headings_nest_by_level(self) -> None:
        """A heading sits under the nearest shallower heading."""
        document = _load("structured.md")

        assert _outline(document) == [
            (1, ""),
            (0, "Platform Guide"),
            (1, "Setup"),
            (2, "Requirements"),
            (3, "Python"),
            (3, "Node"),
            (2, "Install"),
            (1, "Usage"),
            (1, "Setext Heading"),
            (1, "Appendix"),
        ]
        assert [s.parent for s in document.sections] == [
            None,
            None,
            1,
            2,
            3,
            3,
            2,
            1,
            1,
            1,
        ]
        assert document.source_format.value == "markdown"
        assert document.loader_name == "docling"

    def test_the_markdown_suffix_is_read_as_markdown(self) -> None:
        """Docling does not know .markdown, so the loader passes it as .md."""
        document = _load("structured.md", uri="notes.markdown")

        assert document.sections
        assert document.source_format.value == "markdown"

    def test_content_hash_comes_from_the_raw_bytes(self) -> None:
        """The parsed output can change between versions, so it is not hashed."""
        raw = (FIXTURES / "structured.md").read_bytes()

        assert _load("structured.md").content_hash == hashlib.sha256(raw).hexdigest()


class TestOtherFormats:
    """Office and HTML files give sections, tables and figures."""

    @pytest.mark.parametrize(
        "name",
        ["structured.html", "structured.docx", "structured.pptx", "structured.xlsx"],
    )
    def test_every_format_gives_sections_with_content(self, name: str) -> None:
        """Each fixture has at least one unit of content."""
        document = _load(name)

        assert document.sections
        assert sum(len(s.units) for s in document.sections) > 0

    def test_a_table_unit_has_rows(self) -> None:
        """The docx fixture holds one table. Its rows are kept as text."""
        document = _load("structured.docx")

        tables = [
            u for s in document.sections for u in s.units if u.kind == UnitKind.TABLE
        ]
        assert len(tables) == 1
        assert len(tables[0].rows) >= 2
        assert all(isinstance(cell, str) for row in tables[0].rows for cell in row)

    def test_slide_content_keeps_its_page(self) -> None:
        """A pptx unit knows its slide. A docx unit has no page."""
        slides = _load("structured.pptx")
        words = _load("structured.docx")

        assert any(u.pages for s in slides.sections for u in s.units)
        assert not any(u.pages for s in words.sections for u in s.units)

    def test_text_is_not_stored_when_the_option_is_off(self) -> None:
        """The sections go with the text, as for every other loader."""
        document = _load("structured.md", store_text=False)

        assert document.text == ""
        assert document.sections == []
