"""Tests for the checks that Document makes on its sections."""

import pytest

from agrag.common.data_models.document import (
    Document,
    DocumentFamily,
    DocumentSection,
    SourceFormat,
    Unit,
    UnitKind,
)
from agrag.common.data_models.provenance import BoundingBox, PageSpan


def _document(text: str, sections: list[DocumentSection]) -> Document:
    return Document(
        text=text,
        title="t",
        uri="u",
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash="h",
        loader_name="text",
        char_count=len(text),
        sections=sections,
    )


class TestSectionChecks:
    """A Document refuses a section tree that cannot be right."""

    def test_accepts_a_parent_before_its_child(self) -> None:
        """Accepts a parent before its child."""
        sections = [
            DocumentSection(heading="A", depth=1),
            DocumentSection(heading="B", depth=2, parent=0),
        ]

        assert len(_document("", sections).sections) == 2

    @pytest.mark.parametrize("parent", [1, 2, -1])
    def test_rejects_a_parent_that_does_not_come_before(self, parent: int) -> None:
        """Rejects a parent that does not come before."""
        sections = [
            DocumentSection(heading="A", depth=1),
            DocumentSection(heading="B", depth=2, parent=parent),
        ]

        with pytest.raises(ValueError, match="does not come before"):
            _document("", sections)

    def test_rejects_a_child_that_is_not_deeper(self) -> None:
        """Rejects a child that is not deeper."""
        sections = [
            DocumentSection(heading="A", depth=2),
            DocumentSection(heading="B", depth=2, parent=0),
        ]

        with pytest.raises(ValueError, match="deeper than its parent"):
            _document("", sections)


class TestUnitChecks:
    """A unit with offsets must match the document text."""

    def test_rejects_a_unit_that_does_not_match_the_text(self) -> None:
        """Rejects a unit that does not match the text."""
        unit = Unit(kind=UnitKind.PARAGRAPH, text="xyz", char_start=0, char_end=3)
        sections = [DocumentSection(heading="", depth=0, units=[unit])]

        with pytest.raises(ValueError, match="does not match the document text"):
            _document("abc", sections)

    def test_rejects_one_offset_without_the_other(self) -> None:
        """Rejects one offset without the other."""
        with pytest.raises(ValueError, match="set together"):
            Unit(kind=UnitKind.PARAGRAPH, text="a", char_start=0)

    def test_rejects_a_backward_span(self) -> None:
        """Rejects a backward span."""
        with pytest.raises(ValueError, match="char_start <= char_end"):
            Unit(kind=UnitKind.PARAGRAPH, text="a", char_start=3, char_end=1)

    def test_names_section_and_unit_in_a_text_mismatch(self) -> None:
        """A text mismatch names its section and unit."""
        unit = Unit(kind=UnitKind.PARAGRAPH, text="xyz", char_start=0, char_end=3)
        sections = [DocumentSection(heading="", depth=0, units=[unit])]

        with pytest.raises(ValueError, match=r"section 0 unit 0"):
            _document("abc", sections)

    def test_accepts_a_unit_with_no_provenance_channel(self) -> None:
        """A unit with neither offsets nor pages locates by section path."""
        sections = [
            DocumentSection(
                heading="", depth=0, units=[Unit(kind=UnitKind.PARAGRAPH, text="a")]
            )
        ]

        assert _document("a", sections).sections[0].units[0].text == "a"

    def test_rejects_a_page_number_below_one(self) -> None:
        """A page number below one raises."""
        box = BoundingBox(x0=0, y0=0, x1=1, y1=1)
        unit = Unit(
            kind=UnitKind.PARAGRAPH,
            text="a",
            pages=[PageSpan(page_no=0, bbox=box)],
        )
        sections = [DocumentSection(heading="", depth=0, units=[unit])]

        with pytest.raises(ValueError, match=r"section 0 unit 0"):
            _document("a", sections)

    def test_rejects_pages_out_of_order(self) -> None:
        """Pages out of order raise."""
        box = BoundingBox(x0=0, y0=0, x1=1, y1=1)
        unit = Unit(
            kind=UnitKind.PARAGRAPH,
            text="a",
            pages=[PageSpan(page_no=2, bbox=box), PageSpan(page_no=1, bbox=box)],
        )
        sections = [DocumentSection(heading="", depth=0, units=[unit])]

        with pytest.raises(ValueError, match="out of order"):
            _document("a", sections)

    def test_rejects_a_box_with_start_past_end(self) -> None:
        """A box with start past end raises."""
        box = BoundingBox(x0=2, y0=0, x1=1, y1=1)
        unit = Unit(
            kind=UnitKind.PARAGRAPH,
            text="a",
            pages=[PageSpan(page_no=1, bbox=box)],
        )
        sections = [DocumentSection(heading="", depth=0, units=[unit])]

        with pytest.raises(ValueError, match="bbox"):
            _document("a", sections)


class TestUnitTableText:
    """A table or figure carries its caption as its text."""

    def test_header_is_empty_when_no_header_rows_are_marked(self) -> None:
        """No marked header rows give no header."""
        unit = Unit(
            kind=UnitKind.TABLE,
            text="",
            rows=[["h1", "h2"], ["x", "y"]],
            header_rows=0,
        )

        assert unit.header == []

    def test_header_merges_marked_rows(self) -> None:
        """Marked header rows merge into one name for each column."""
        unit = Unit(
            kind=UnitKind.TABLE,
            text="",
            rows=[["Total", "Revenue"], ["2024", "Q1"], ["a", "b"]],
            header_rows=2,
        )

        assert unit.header == ["Total 2024", "Revenue Q1"]

    @pytest.mark.parametrize("kind", [UnitKind.TABLE, UnitKind.FIGURE])
    def test_rejects_text_that_differs_from_the_caption(self, kind: UnitKind) -> None:
        """Text that differs from the caption raises."""
        with pytest.raises(ValueError, match="must equal its caption"):
            Unit(kind=kind, text="body", caption="cap")

    @pytest.mark.parametrize("kind", [UnitKind.TABLE, UnitKind.FIGURE])
    def test_accepts_caption_text_and_empty_text_without_a_caption(
        self, kind: UnitKind
    ) -> None:
        """Caption text and empty text without a caption both pass."""
        assert Unit(kind=kind, text="cap", caption="cap").text == "cap"
        assert Unit(kind=kind, text="").text == ""
