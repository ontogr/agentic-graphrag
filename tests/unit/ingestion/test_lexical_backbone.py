"""Tests for the pure Document/PART_OF record-construction helpers.

Every function here is pure: no GraphStore mocking, plain data in and
RelationRecord/NodeRecord out.
"""

from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import (
    DOCUMENT_LABEL,
    Document,
    DocumentFamily,
    SourceFormat,
)
from agrag.common.data_models.provenance import TextProvenance
from agrag.ingestion._lexical_backbone import (
    build_document_record,
    build_next_chunk_records,
    build_part_of_records,
    distinct_documents,
)
from agrag.ingestion.merge import next_chunk_id, part_of_id


def _doc(*, uri: str = "u", document_key: str | None = None) -> Document:
    return Document(
        text="hello",
        title="t",
        uri=uri,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        # content_hash tracks uri so distinct uris also get distinct
        # resolved ids, matching what a real loader would produce.
        content_hash=uri,
        loader_name="text",
        char_count=5,
        line_count=1,
        document_key=document_key,
    )


def _chunk(document_id: UUID, text: str = "hello", index: int = 0) -> Chunk:
    return Chunk(
        document_id=document_id,
        index=index,
        text=text,
        provenance=TextProvenance(char_start=0, char_end=len(text)),
    )


class TestDistinctDocuments:
    """distinct_documents dedupes by resolved_id, keeping first occurrence."""

    def test_deduplicates_by_resolved_id(self) -> None:
        """The same document appearing twice yields one entry."""
        doc = _doc()
        result = distinct_documents([doc, doc])
        assert result == [doc]

    def test_keeps_all_distinct_documents(self) -> None:
        """Two distinct documents both appear, in first-seen order."""
        first, second = _doc(uri="a"), _doc(uri="b")
        result = distinct_documents([first, second])
        assert result == [first, second]


class TestBuildDocumentRecord:
    """build_document_record delegates to Document.to_node_record."""

    def test_produces_expected_shape(self) -> None:
        """The record carries the document's node id, label, and properties."""
        doc = _doc(document_key="doc-key")
        record = build_document_record(doc)
        assert record.id == Document.node_id_for(document_key="doc-key")
        assert record.labels == [DOCUMENT_LABEL]
        assert record.properties["document_key"] == "doc-key"

    def test_same_document_key_returns_same_id(self) -> None:
        """Two documents with the same document_key converge on one node id."""
        first = build_document_record(_doc(uri="a", document_key="shared"))
        second = build_document_record(_doc(uri="b", document_key="shared"))
        assert first.id == second.id


class TestBuildPartOfRecords:
    """build_part_of_records links one document node to its chunks."""

    def test_one_record_per_chunk(self) -> None:
        """An N-chunk document produces exactly N PART_OF records."""
        document_id = uuid4()
        document_node_id = uuid4()
        chunks = [_chunk(document_id), _chunk(document_id), _chunk(document_id)]
        records = build_part_of_records(document_node_id, chunks)
        assert len(records) == 3

    def test_records_are_open(self) -> None:
        """Every record has valid_at set and invalid_at unset."""
        document_id = uuid4()
        document_node_id = uuid4()
        [record] = build_part_of_records(document_node_id, [_chunk(document_id)])
        assert record.properties["valid_at"] is not None
        assert record.properties["invalid_at"] is None

    def test_record_endpoints_and_type(self) -> None:
        """Each record points Document -[:PART_OF]-> Chunk with the right id."""
        document_id = uuid4()
        document_node_id = uuid4()
        chunk = _chunk(document_id)
        [record] = build_part_of_records(document_node_id, [chunk])
        assert record.type == "PART_OF"
        assert record.start_id == document_node_id
        assert record.end_id == chunk.id
        assert chunk.id is not None
        assert record.id == part_of_id(document_node_id, chunk.id)

    def test_never_cross_links_distinct_documents(self) -> None:
        """Chunks from two documents each link only to their own document node."""
        doc_a_id, doc_b_id = uuid4(), uuid4()
        node_a, node_b = uuid4(), uuid4()
        chunk_a = _chunk(doc_a_id)
        chunk_b = _chunk(doc_b_id)

        records_a = build_part_of_records(node_a, [chunk_a])
        records_b = build_part_of_records(node_b, [chunk_b])

        assert records_a[0].start_id == node_a
        assert records_a[0].end_id == chunk_a.id
        assert records_b[0].start_id == node_b
        assert records_b[0].end_id == chunk_b.id


class TestBuildNextChunkRecords:
    """build_next_chunk_records links adjacent chunks per document."""

    def test_orders_chunks_and_keeps_documents_separate(self) -> None:
        """Edges follow chunk indexes and never cross document boundaries."""
        first_document, second_document = uuid4(), uuid4()
        first = _chunk(first_document, "first", index=1)
        previous = _chunk(first_document, "previous", index=0)
        other = _chunk(second_document, "other", index=0)

        records = build_next_chunk_records([first, other, previous])

        assert len(records) == 1
        assert records[0].start_id == previous.id
        assert records[0].end_id == first.id
        assert records[0].id == next_chunk_id(previous.id, first.id)

    def test_rejects_unresolved_chunk_ids(self) -> None:
        """An unresolved adjacent chunk cannot produce a deterministic edge."""
        document_id = uuid4()
        chunk = _chunk(document_id, index=0)
        chunk.id = None

        with pytest.raises(ValueError, match="Chunk.id"):
            build_next_chunk_records([chunk, _chunk(document_id, index=1)])
