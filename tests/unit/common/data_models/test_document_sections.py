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
