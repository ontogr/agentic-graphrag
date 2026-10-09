"""Tests for splitting one add() call's work into per-document slices."""

import logging
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.extraction import ExtractedEntity, ExtractedRelation
from agrag.common.data_models.provenance import TextProvenance
from agrag.ingestion._ingest import _group_by_document


LOGGER_NAME = "agrag.ingestion._ingest"


def _doc(*, key: str, text: str = "hello world") -> Document:
    return Document(
        text=text,
        title="t",
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=f"hash-{key}-{text}",
        loader_name="text",
        char_count=len(text),
        line_count=1,
    )


def _chunk(document: Document, *, index: int = 0, text: str = "hello world") -> Chunk:
    return Chunk(
        id=uuid4(),
        document_id=Document.node_id_for(document_key=document.resolved_document_key),
        index=index,
        text=text,
        provenance=TextProvenance(char_start=0, char_end=len(text)),
    )


def _entity(chunk: Chunk, text: str) -> ExtractedEntity:
    return ExtractedEntity(
        chunk_id=chunk.id,
        label="Organization",
        text=text,
        char_start=0,
        char_end=len(text),
    )


def _relation(
    chunk: Chunk, *, label: str, source_index: int, target_index: int
) -> ExtractedRelation:
    return ExtractedRelation(
        chunk_id=chunk.id,
        label=label,
        source_index=source_index,
        target_index=target_index,
    )


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == LOGGER_NAME and record.levelno == logging.WARNING
    ]


class TestGroupByDocument:
    """Splitting one add() call into per-document slices."""

    def test_warns_and_joins_first_slice_when_chunk_document_is_unlisted(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """An unlisted document falls back to the first slice with a warning."""
        listed = _doc(key="listed")
        unlisted_chunk = _chunk(_doc(key="unlisted"))

        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            slices = _group_by_document([unlisted_chunk], [listed], [], [], [])

        assert len(slices) == 1
        _, slice_chunks, _, _, _, _ = slices[0]
        assert slice_chunks == [unlisted_chunk]
        assert len(_warnings(caplog)) == 1

    def test_warns_and_drops_relation_whose_endpoints_span_documents(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A relation across two documents is dropped with a warning.

        A relation inside one document is kept, with its indices remapped to
        that document's slice.
        """
        doc_a = _doc(key="a")
        doc_b = _doc(key="b")
        chunk_a = _chunk(doc_a)
        chunk_b = _chunk(doc_b)
        entities = [
            _entity(chunk_a, "Alice"),
            _entity(chunk_a, "Acme"),
            _entity(chunk_b, "Bob"),
        ]
        relations = [
            _relation(chunk_a, label="WORKS_AT", source_index=0, target_index=1),
            _relation(chunk_a, label="KNOWS", source_index=1, target_index=2),
        ]

        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            slices = _group_by_document(
                [chunk_a, chunk_b], [doc_a, doc_b], entities, relations, []
            )

        relations_by_key = {
            key: slice_relations for key, _, _, _, slice_relations, _ in slices
        }
        assert [
            (rel.label, rel.source_index, rel.target_index)
            for rel in relations_by_key["a"]
        ] == [("WORKS_AT", 0, 1)]
        assert relations_by_key["b"] == []
        warnings = _warnings(caplog)
        assert len(warnings) == 1
        assert "KNOWS" in warnings[0]
