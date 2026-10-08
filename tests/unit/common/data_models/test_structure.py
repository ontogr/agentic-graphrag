"""Tests for the section keys, node ids, reading order and ancestry of a Document."""

import pytest

from agrag.common.data_models.document import DocumentSection
from agrag.common.data_models.structure import (
    chunk_id,
    common_ancestor,
    heading_paths,
    node_id,
    reading_positions,
    section_keys,
    version_id,
)
from tests.unit.chunking._section_support import paragraph, sectioned_document


def _tree() -> list[DocumentSection]:
    return [
        DocumentSection(heading="Intro", depth=1, units=[paragraph("a")]),
        DocumentSection(heading="Method", depth=1, units=[paragraph("b")]),
        DocumentSection(
            heading="Data", depth=2, parent=1, units=[paragraph("c"), paragraph("d")]
        ),
        DocumentSection(heading="Model", depth=2, parent=1),
        DocumentSection(heading="Results", depth=1),
    ]


class TestSectionKeys:
    """A section key follows the heading path, not the content."""

    def test_keys_ignore_the_content_version(self) -> None:
        """An edit that keeps the headings keeps every key."""
        first = sectioned_document(_tree(), content_hash="v1")
        second = sectioned_document(_tree(), content_hash="v2")

        assert section_keys(first) == section_keys(second)

    def test_a_renamed_heading_changes_its_key_and_its_children(self) -> None:
        """Renaming a section changes the keys of the section and of what it holds."""
        renamed = _tree()
        renamed[1] = renamed[1].model_copy(update={"heading": "Methods"})

        before = section_keys(sectioned_document(_tree()))
        after = section_keys(sectioned_document(renamed))

        assert before[0] == after[0]
        assert before[1] != after[1]
        assert before[2] != after[2]
        assert before[4] == after[4]

    def test_sections_with_the_same_path_get_different_keys(self) -> None:
        """Two sibling sections with one title are told apart by their order."""
        twins = [
            DocumentSection(heading="Note", depth=1),
            DocumentSection(heading="Note", depth=1),
        ]

        keys = section_keys(sectioned_document(twins))

        assert keys[0] != keys[1]


class TestIds:
    """Node ids change with the version. Keys do not."""

    def test_node_id_depends_on_key_and_version(self) -> None:
        """Node id depends on key and version."""
        key = section_keys(sectioned_document(_tree()))[0]

        assert node_id(key, "v1") == node_id(key, "v1")
        assert node_id(key, "v1") != node_id(key, "v2")

    def test_version_id_follows_the_content_hash(self) -> None:
        """Version id follows the content hash."""
        first = version_id(sectioned_document([], content_hash="a"))
        second = version_id(sectioned_document([], content_hash="b"))

        assert first != second

    def test_chunk_id_follows_every_input(self) -> None:
        """Chunk id follows every input."""
        document_id = node_id(section_keys(sectioned_document(_tree()))[0], "v1")
        base = chunk_id(document_id, "v1", "hash", 0)

        assert base == chunk_id(document_id, "v1", "hash", 0)
        assert base != chunk_id(document_id, "v2", "hash", 0)
        assert base != chunk_id(document_id, "v1", "other", 0)
        assert base != chunk_id(document_id, "v1", "hash", 1)


class TestReadingPositions:
    """Headings and units share one counter in reading order."""

    def test_numbers_each_heading_and_unit_once(self) -> None:
        """Numbers each heading and unit once."""
        headings, units = reading_positions(sectioned_document(_tree()))

        assert headings == [0, 2, 4, 7, 8]
        assert units == [[1], [3], [5, 6], [], []]


class TestHeadingPaths:
    """A path holds the headings from the top, without empty ones."""

    def test_skips_empty_headings(self) -> None:
        """Skips empty headings."""
        sections = [
            DocumentSection(heading="", depth=0),
            DocumentSection(heading="A", depth=1),
            DocumentSection(heading="B", depth=2, parent=1),
        ]

        assert heading_paths(sections) == [[], ["A"], ["A", "B"]]


class TestCommonAncestor:
    """The lowest section that contains all the given sections."""

    @pytest.mark.parametrize(
        ("indexes", "expected"),
        [
            ([2], 2),
            ([2, 3], 1),
            ([1, 2], 1),
            ([0, 2], None),
            ([2, 4], None),
        ],
    )
    def test_finds_the_lowest_container(
        self, indexes: list[int], expected: int | None
    ) -> None:
        """Finds the lowest container."""
        assert common_ancestor(_tree(), indexes) == expected
