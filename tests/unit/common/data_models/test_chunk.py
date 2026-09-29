"""Tests for the Chunk model's graph-node record.

Covers the chunker fields: they reach the record when set and stay out of it when
unset, so a chunk written before chunkers were recorded looks the same as before.
"""

from uuid import uuid4

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.provenance import TextProvenance


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
