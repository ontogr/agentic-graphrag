"""Tests for the Document domain model's graph-node identity and persistence.

Covers ``node_id_for``'s collision resistance, ``document_key`` defaulting to
``uri``, ``Document.id`` following the node id of the document key, and
``to_node_record()`` omitting the document body.
"""

from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from agrag.common.data_models.document import (
    Document,
    DocumentFamily,
    DocumentSection,
    SourceFormat,
    Unit,
    UnitKind,
)


def _doc(**fields: Any) -> Document:
    values: dict[str, Any] = {
        "text": "hello world",
        "title": "t",
        "uri": "u",
        "source_format": SourceFormat.TXT,
        "family": DocumentFamily.PROSE,
        "content_hash": "h",
        "loader_name": "text",
        "char_count": 11,
        "line_count": 1,
    }
    return Document(**(values | fields))


class TestNodeIdFor:
    """node_id_for maps distinct document keys to distinct ids."""

    @pytest.mark.parametrize(
        ("key_a", "key_b"),
        [
            ("doc-a", "doc-b"),
            ("path/to/file.txt", "path/to/other.txt"),
            ("", "doc-a"),
        ],
    )
    def test_distinct_keys_never_collide(self, key_a: str, key_b: str) -> None:
        """Distinct keys never return the same id."""
        assert Document.node_id_for(document_key=key_a) != Document.node_id_for(
            document_key=key_b
        )


class TestDocumentId:
    """Document.id is the persisted Document node id of its document key."""

    @pytest.mark.parametrize(
        "fields",
        [
            pytest.param({"uri": "inline://abc"}, id="inline"),
            pytest.param({"uri": "notes.txt"}, id="file"),
            pytest.param(
                {
                    "uri": "rows.csv",
                    "family": DocumentFamily.RECORD,
                    "record_index": 3,
                },
                id="record-row",
            ),
            pytest.param(
                {
                    "uri": "rows.csv",
                    "family": DocumentFamily.RECORD,
                    "record_index": 3,
                    "record_id": "row-3",
                },
                id="record-with-id",
            ),
        ],
    )
    def test_id_is_the_node_id_of_the_document_key(self, fields: dict) -> None:
        """The id of every kind of document is its node id."""
        document = _doc(**fields)

        assert document.id == Document.node_id_for(
            document_key=document.resolved_document_key
        )

    def test_identical_text_under_different_keys_gets_different_ids(self) -> None:
        """Two documents with the same text but different keys keep distinct ids."""
        first = _doc(uri="a.txt")
        second = _doc(uri="b.txt")

        assert first.content_hash == second.content_hash
        assert first.id != second.id

    def test_rejects_an_explicit_id_that_is_not_the_node_id(self) -> None:
        """An explicit id must match the id of the document key."""
        with pytest.raises(ValidationError, match="does not match"):
            Document(
                id=uuid4(),
                text="hello world",
                title="t",
                uri="u",
                source_format=SourceFormat.TXT,
                family=DocumentFamily.PROSE,
                content_hash="h",
                loader_name="text",
                char_count=11,
                line_count=1,
            )


class TestResolvedDocumentKey:
    """resolved_document_key defaults to uri unless explicitly supplied."""

    @pytest.mark.parametrize(
        ("document_key", "expected"),
        [
            (None, "u"),
            ("explicit-key", "explicit-key"),
        ],
    )
    def test_defaults_to_uri_unless_supplied(
        self, document_key: str | None, expected: str
    ) -> None:
        """document_key defaults to uri; an explicit value is left untouched."""
        doc = _doc(uri="u", document_key=document_key)
        assert doc.document_key == expected
        assert doc.resolved_document_key == expected


class TestToNodeRecord:
    """to_node_record() builds the persisted Document node's write shape."""

    def test_excludes_text(self) -> None:
        """The record never carries the full document body."""
        record = _doc().to_node_record()
        assert "text" not in record.properties


def _sectioned(text: str, spans: list[tuple[int, int]]) -> Document:
    units = [
        Unit(
            kind=UnitKind.PARAGRAPH,
            text=text[start:end],
            char_start=start,
            char_end=end,
        )
        for start, end in spans
    ]
    return Document(
        text=text,
        title="t",
        uri="u",
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash="h",
        loader_name="text",
        char_count=len(text),
        sections=[DocumentSection(heading="", depth=0, units=units)],
    )


class TestSectionSpanOrder:
    """Unit spans run in reading order inside the document text."""

    def test_rejects_spans_outside_the_text(self) -> None:
        """A span past the end of the text raises."""
        with pytest.raises(ValidationError, match="outside the document text"):
            _sectioned("hello world", [(0, 5), (6, 60)])

    def test_rejects_spans_out_of_reading_order(self) -> None:
        """A span starting before the previous unit ends raises."""
        with pytest.raises(ValidationError, match="before the previous unit ends"):
            _sectioned("one two", [(4, 7), (0, 3)])
