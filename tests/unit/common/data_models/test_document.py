"""Tests for the Document domain model's graph-node identity and persistence.

Covers ``node_id_for``'s collision resistance, ``document_key`` defaulting to
``uri``, and ``to_node_record()`` omitting the document body.
"""

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


def _doc(*, uri: str = "u", document_key: str | None = None) -> Document:
    return Document(
        text="hello world",
        title="t",
        uri=uri,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash="h",
        loader_name="text",
        char_count=11,
        line_count=1,
        document_key=document_key,
    )


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


class TestRawRecord:
    """raw_record holds JSON data only."""

    def _doc_with_record(self, raw_record: object) -> Document:
        data = _doc().model_dump()
        data["raw_record"] = raw_record
        return Document.model_validate(data)

    def test_accepts_nested_json_values(self) -> None:
        """Nested lists and objects pass."""
        doc = self._doc_with_record({"tags": ["a", 1], "meta": {"n": None}})

        assert doc.raw_record == {"tags": ["a", 1], "meta": {"n": None}}

    def test_rejects_a_non_json_value(self) -> None:
        """A non-JSON value raises."""
        with pytest.raises(ValidationError):
            self._doc_with_record({"when": object()})


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
