"""Tests for the Chunk model's graph-node record.

Covers the chunker fields: they reach the record when set and stay out of it when
unset, so a chunk written before chunkers were recorded looks the same as before.
"""

from uuid import UUID, uuid4

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
