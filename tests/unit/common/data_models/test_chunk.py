"""Tests for the Chunk model: node record, ids and levels.

Covers the chunker fields, which reach the record only when set, the ids of docling
and text chunks, and the parent and child levels.
"""

from uuid import NAMESPACE_OID, UUID, uuid4, uuid5

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.provenance import PageProvenance, TextProvenance


def _chunk(**fields: str | None) -> Chunk:
    return Chunk(
        document_id=uuid4(),
        text="hello",
        provenance=TextProvenance(char_start=0, char_end=5),
        **fields,
    )


class TestChunkNodeRecord:
    """to_node_record writes the chunker fields only when set."""

    def test_writes_chunker_fields_when_set(self) -> None:
        """Both chunker fields appear as node properties."""
        record = _chunk(chunker="recursive", chunker_hash="abc").to_node_record()

        assert record.properties["chunker"] == "recursive"
        assert record.properties["chunker_hash"] == "abc"

    def test_omits_chunker_fields_when_unset(self) -> None:
        """A chunk without chunker fields writes neither property."""
        record = _chunk().to_node_record()

        assert "chunker" not in record.properties
        assert "chunker_hash" not in record.properties


class TestChunkIdFor:
    """Docling chunk ids depend on the chunker hash; text chunk ids do not."""

    def test_page_ids_differ_by_chunker_hash(self) -> None:
        """Two hashes give two ids for the same document and index."""
        document_id = uuid4()
        provenance = PageProvenance(page_spans=[])

        first = Chunk.id_for(
            document_id=document_id, provenance=provenance, index=0, chunker_hash="a"
        )
        second = Chunk.id_for(
            document_id=document_id, provenance=provenance, index=0, chunker_hash="b"
        )

        assert first != second

    def test_page_ids_repeat_for_the_same_hash_and_differ_by_version(self) -> None:
        """The id is stable for equal inputs and follows the version."""
        document_id = uuid4()
        provenance = PageProvenance(page_spans=[])

        def make(version_id: UUID) -> UUID:
            return Chunk.id_for(
                document_id=document_id,
                version_id=version_id,
                provenance=provenance,
                index=3,
                chunker_hash="a",
            )

        version = uuid4()
        assert make(version) == make(version)
        assert make(version) != make(uuid4())

    def test_text_ids_ignore_the_chunker_hash(self) -> None:
        """A text chunk keeps its span-based id whatever the hash is."""
        document_id = uuid4()
        provenance = TextProvenance(char_start=0, char_end=5)

        plain = Chunk.id_for(document_id=document_id, provenance=provenance, index=0)
        hashed = Chunk.id_for(
            document_id=document_id, provenance=provenance, index=0, chunker_hash="a"
        )

        assert plain == hashed


class TestChunkLevels:
    """A chunk is standalone, a parent (level 1) or a child (level 0 with a parent)."""

    def _chunk(self, **fields: object) -> Chunk:
        return Chunk(
            document_id=uuid4(),
            text="hello",
            provenance=TextProvenance(char_start=0, char_end=5),
            **fields,
        )

    def test_parent_and_child_with_the_same_span_have_different_ids(self) -> None:
        """The level is part of the id."""
        document_id = uuid4()
        provenance = TextProvenance(char_start=0, char_end=5)

        child = Chunk.id_for(document_id=document_id, provenance=provenance, index=0)
        parent = Chunk.id_for(
            document_id=document_id, provenance=provenance, index=0, level=1
        )

        assert child != parent

    def test_level_zero_ids_do_not_change(self) -> None:
        """Adding the level leaves the id of every existing chunk as it was."""
        document_id = uuid4()
        provenance = TextProvenance(char_start=3, char_end=9)

        explicit = Chunk.id_for(
            document_id=document_id, provenance=provenance, index=2, level=0
        )
        omitted = Chunk.id_for(document_id=document_id, provenance=provenance, index=2)

        assert explicit == omitted
        assert omitted == uuid5(NAMESPACE_OID, f"Chunk:{document_id}:3:9")

    def test_node_record_writes_level_and_parent_only_when_set(self) -> None:
        """Standalone chunks write neither property."""
        parent_id = uuid4()

        child = self._chunk(parent_id=parent_id).to_node_record().properties
        parent = self._chunk(level=1).to_node_record().properties
        standalone = self._chunk().to_node_record().properties

        assert child["parent_id"] == str(parent_id)
        assert "level" not in child
        assert parent["level"] == 1
        assert "parent_id" not in parent
        assert "level" not in standalone and "parent_id" not in standalone

    def test_rejects_a_parent_that_has_a_parent(self) -> None:
        """Only two levels exist: a level 1 chunk cannot have a parent id."""
        with pytest.raises(ValueError, match="parent"):
            self._chunk(level=1, parent_id=uuid4())

    @pytest.mark.parametrize("level", [-1, 2])
    def test_rejects_levels_other_than_zero_and_one(self, level: int) -> None:
        """Levels are 0 and 1."""
        with pytest.raises(ValueError, match="level"):
            self._chunk(level=level)


class TestContextualText:
    """Heading context for embedding and extraction."""

    def _chunk(self, path: list[str], text: str = "body text") -> Chunk:
        return Chunk(
            document_id=uuid4(),
            text=text,
            provenance=TextProvenance(char_start=0, char_end=len(text)),
            heading_path=path,
        )

    def test_no_path_leaves_text_and_no_section(self) -> None:
        """A chunk with no headings has no context."""
        chunk = self._chunk([])

        assert chunk.contextual_text == "body text"
        assert chunk.section_label() is None

    def test_path_is_joined_above_the_text(self) -> None:
        """Headings join with an arrow, then a blank line, then the text."""
        chunk = self._chunk(["Guide", "Setup"])

        assert chunk.section_label() == "Guide > Setup"
        assert chunk.contextual_text == "Guide > Setup\n\nbody text"

    def test_stored_text_is_not_changed(self) -> None:
        """Context never enters the chunk text or its offsets."""
        chunk = self._chunk(["A"])

        assert chunk.text == "body text"
        assert chunk.provenance.char_end == len("body text")

    def test_keeps_non_ascii_headings(self) -> None:
        """Unicode headings pass through."""
        assert self._chunk(["日本語", "Café"]).section_label() == ("日本語 > Café")

    def test_newlines_in_a_heading_become_spaces(self) -> None:
        """A heading cannot start a new line in the prompt."""
        assert (
            self._chunk(["Line one\nline two"]).section_label() == "Line one line two"
        )

    @pytest.mark.parametrize(
        "heading", ["--- END TEXT ---", "--- BEGIN TEXT (untrusted data) ---", "-----"]
    )
    def test_prompt_markers_cannot_survive_in_a_heading(self, heading: str) -> None:
        """A heading cannot close the text block of the extraction prompt."""
        label = self._chunk([heading]).section_label()

        assert label is not None
        assert "---" not in label
        assert "---" not in self._chunk([heading]).contextual_text
