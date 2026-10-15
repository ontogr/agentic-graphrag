"""Tests for the Chunk model: node record and ids.

Covers the chunker and section fields, which reach the record only when set.
"""

import hashlib
from uuid import uuid4

import pytest
from pydantic import ValidationError

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.provenance import TextProvenance


def _chunk(**fields: object) -> Chunk:
    fields.setdefault("content_hash", hashlib.sha256(b"hello").hexdigest())
    return Chunk(
        id=uuid4(),
        document_id=uuid4(),
        text="hello",
        provenance=TextProvenance(char_start=0, char_end=5),
        **fields,  # type: ignore[arg-type]
    )


class TestChunkContentHash:
    """A chunk must name the content version it was cut from."""

    def test_construction_requires_content_hash(self) -> None:
        """A chunk built without a content hash fails validation."""
        with pytest.raises(ValidationError, match="content_hash"):
            Chunk.model_validate(
                {
                    "id": uuid4(),
                    "document_id": uuid4(),
                    "text": "hello",
                    "provenance": TextProvenance(char_start=0, char_end=5),
                }
            )

    @pytest.mark.parametrize(
        "content_hash",
        ["a" * 63, "a" * 65, "g" * 64, "A" * 64],
        ids=["short", "long", "non-hex", "uppercase"],
    )
    def test_rejects_content_hashes_that_are_not_lowercase_sha256(
        self, content_hash: str
    ) -> None:
        """Only 64-character lowercase hexadecimal digests are accepted."""
        with pytest.raises(ValidationError, match="content_hash"):
            _chunk(content_hash=content_hash)

    def test_accepts_a_lowercase_sha256_digest(self) -> None:
        """A 64-character lowercase hexadecimal digest is accepted unchanged."""
        digest = "a" * 64

        assert _chunk(content_hash=digest).content_hash == digest


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


class TestSectionIds:
    """to_node_record writes the covered sections only when there are some."""

    def test_writes_section_ids_when_set(self) -> None:
        """The ids are stored as strings."""
        section = uuid4()
        record = _chunk().model_copy(update={"section_ids": [section]}).to_node_record()

        assert record.properties["section_ids"] == [str(section)]

    def test_omits_section_ids_when_empty(self) -> None:
        """A chunk with no sections writes no property."""
        assert "section_ids" not in _chunk().to_node_record().properties


class TestContextualText:
    """Heading context for embedding and extraction."""

    def _chunk(self, path: list[str], text: str = "body text") -> Chunk:
        return Chunk(
            id=uuid4(),
            document_id=uuid4(),
            text=text,
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
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
