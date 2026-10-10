"""Tests for the pure document dedupe and NEXT_CHUNK record helpers.

Every function here is pure: no GraphStore mocking, plain data in and
RelationRecord/NodeRecord out.
"""

from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import (
    Document,
    DocumentFamily,
    SourceFormat,
)
from agrag.common.data_models.provenance import TextProvenance
from agrag.ingestion._lexical_backbone import (
    build_next_chunk_records,
    distinct_documents,
)
from agrag.ingestion.merge import next_chunk_id


def _doc(
    *, uri: str = "u", document_key: str | None = None, title: str = "t"
) -> Document:
    return Document(
        text="hello",
        title=title,
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


def _chunk(
    document_id: UUID,
    text: str = "hello",
    index: int = 0,
    start: int = 0,
) -> Chunk:
    return Chunk(
        id=uuid4(),
        document_id=document_id,
        index=index,
        text=text,
        provenance=TextProvenance(char_start=start, char_end=start + len(text)),
    )


class TestDistinctDocuments:
    """distinct_documents dedupes by resolved_id, keeping first occurrence."""

    def test_deduplicates_by_resolved_id(self) -> None:
        """The same document appearing twice yields one entry."""
        first = _doc(document_key="shared", title="first")
        second = _doc(document_key="shared", title="second")
        result = distinct_documents([first, second])
        assert result == [first]
        assert result[0].title == "first"


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

    def test_sections_and_table_chunks_share_one_document_chain(self) -> None:
        """document_id alone decides the chain, not section or content kind."""
        document_id = uuid4()
        chunks = [
            _chunk(document_id, f"c{i}", index=i).model_copy(
                update={"section_ids": [uuid4()]}
            )
            for i in range(4)
        ]
        chunks[2] = chunks[2].model_copy(update={"content_kind": "table"})

        records = build_next_chunk_records([chunks[3], chunks[0], chunks[2], chunks[1]])

        assert [(r.start_id, r.end_id) for r in records] == [
            (chunks[0].id, chunks[1].id),
            (chunks[1].id, chunks[2].id),
            (chunks[2].id, chunks[3].id),
        ]

    def test_rejects_unresolved_chunk_ids(self) -> None:
        """An unresolved adjacent chunk cannot produce a deterministic edge."""
        document_id = uuid4()
        chunk = _chunk(document_id, index=0)
        chunk.id = None

        with pytest.raises(ValueError, match="Chunk.id"):
            build_next_chunk_records([chunk, _chunk(document_id, index=1)])
