"""Tests for heading depth from dotted numbers."""

import pytest
from docling_core.types.doc import DoclingDocument

from agrag.loaders.docling._pdf_levels import numbered_depths, numbering_depth
from agrag.loaders.docling._sections import read_body


def _document(headings: list[tuple[str, int]]) -> DoclingDocument:
    doc = DoclingDocument(name="t")
    for text, level in headings:
        doc.add_heading(text=text, level=level)
    return doc


class TestNumberingDepth:
    """The depth is the count of dotted parts."""

    @pytest.mark.parametrize(
        ("heading", "depth"),
        [
            ("1 Introduction", 1),
            ("2.1 Training Deep Networks", 2),
            ("5.4.1 Optimal Architecture", 3),
            ("3. Methods", 1),
            ("4) Results", 1),
            ("Abstract", None),
            ("110th", None),
            ("Figure 1.1. Overview", None),
            ("A Contributions", None),
        ],
    )
    def test_reads_the_leading_number(self, heading: str, depth: int | None) -> None:
        """Only a number at the start counts."""
        assert numbering_depth(heading) == depth


class TestNumberedDepths:
    """Numbering is used only when it is the one signal."""

    def test_numbered_headings_get_their_depth_and_others_are_left_alone(self) -> None:
        """Unnumbered headings stay at depth 1 by getting no entry."""
        doc = _document(
            [("Abstract", 1), ("1 Intro", 1), ("1.1 Scope", 1), ("2 Method", 1)]
        )

        depths = numbered_depths(read_body(doc))

        assert sorted(depths.values()) == [1, 1, 2]
        assert len(depths) == 3

    def test_no_depths_when_a_bookmark_already_gave_a_level(self) -> None:
        """A level above 1 means Docling matched a bookmark."""
        doc = _document([("1 A", 1), ("1.1 B", 2), ("2 C", 1)])

        assert numbered_depths(read_body(doc)) == {}

    def test_no_depths_when_less_than_half_are_numbered(self) -> None:
        """Mostly unnumbered documents stay flat."""
        doc = _document([("Intro", 1), ("Body", 1), ("1 Notes", 1), ("Summary", 1)])

        assert numbered_depths(read_body(doc)) == {}

    def test_no_depths_for_fewer_than_three_headings(self) -> None:
        """Too few headings to trust."""
        assert numbered_depths(read_body(_document([("1 A", 1), ("2 B", 1)]))) == {}
