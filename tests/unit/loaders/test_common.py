"""Tests for shared reader helpers in agrag.loaders._common.

Covers Document id derivation (content hash versus an explicit record id,
and that identical text still gets distinct ids by row position or source
uri when no record id or source hash disambiguates it), read_within_limit
rejecting a non-positive ``max_document_bytes``, resolve_text_column's
named-column and known-default-column resolution, and build_record_document
producing well-formed documents (null-field normalization, title-column
fallback, and rejecting a missing or null configured id column).
"""

from io import BytesIO

import pytest

from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.loaders.common import (
    build_record_document,
    paragraph_units,
    read_within_limit,
    resolve_text_column,
)
from agrag.loaders.errors import MalformedRecordError
from agrag.loaders.types import DecodedText, ReadOptions, SourceRef


def _ref(extension: str) -> SourceRef:
    return SourceRef(uri=f"file{extension}", extension=extension, byte_size=10)


def _decoded(text: str) -> DecodedText:
    return DecodedText(
        text=text,
        encoding="utf-8",
        had_bom=False,
        content_hash="h",
        char_count=len(text),
        line_count=text.count("\n") + 1,
    )


class TestDocumentId:
    """The document id resolves from content hash or record id."""

    def test_record_id_overrides_content_hash(self) -> None:
        """Record id overrides content hash."""
        base = {
            "text": "x",
            "title": "t",
            "uri": "u",
            "source_format": SourceFormat.CSV,
            "family": DocumentFamily.RECORD,
            "content_hash": "abc",
            "loader_name": "csv",
            "char_count": 1,
            "line_count": 1,
            "record_index": 0,
        }
        by_hash = Document(**base)
        by_record = Document(**base, record_id="R1")
        assert by_hash.id != by_record.id

    def test_duplicate_record_text_gets_distinct_ids_without_a_record_id(self) -> None:
        """Two rows with identical text still get distinct ids by row position."""
        base = {
            "text": "same text",
            "title": "t",
            "uri": "u",
            "source_format": SourceFormat.CSV,
            "family": DocumentFamily.RECORD,
            "content_hash": "dup",
            "loader_name": "csv",
            "char_count": 9,
            "line_count": 1,
            "source_hash": "s",
        }
        first = Document(**base, record_index=0)
        second = Document(**base, record_index=1)
        assert first.id != second.id

    def test_identical_rows_from_different_sources_get_distinct_ids(self) -> None:
        """Two sources without source_hash still get distinct ids, via uri."""
        base = {
            "text": "same text",
            "title": "t",
            "source_format": SourceFormat.CSV,
            "family": DocumentFamily.RECORD,
            "content_hash": "dup",
            "loader_name": "csv",
            "char_count": 9,
            "line_count": 1,
            "record_index": 0,
        }
        first = Document(**base, uri="a.csv")
        second = Document(**base, uri="b.csv")
        assert first.id != second.id


class TestReadWithinLimit:
    """The shared read helper enforces a usable, positive byte limit."""

    def test_rejects_a_negative_limit_instead_of_reading_unbounded(self) -> None:
        """A negative limit must not fall through to an unbounded stream read."""
        opts = ReadOptions(max_document_bytes=-2)
        stream = BytesIO(b"x" * 10)
        with pytest.raises(ValueError, match="max_document_bytes"):
            read_within_limit(stream, _ref(".txt"), opts)

    def test_rejects_a_zero_limit(self) -> None:
        """A limit of zero is degenerate and must not silently pass through."""
        opts = ReadOptions(max_document_bytes=0)
        stream = BytesIO(b"x")
        with pytest.raises(ValueError, match="max_document_bytes"):
            read_within_limit(stream, _ref(".txt"), opts)


class TestResolveTextColumn:
    """The text column resolves by name or by a known default."""

    def test_uses_named_column(self) -> None:
        """Uses named column."""
        assert resolve_text_column(["a", "b"], "b") == "b"

    def test_missing_named_column_raises(self) -> None:
        """Missing named column raises."""
        try:
            resolve_text_column(["a", "b"], "z")
        except MalformedRecordError:
            return
        raise AssertionError("expected MalformedRecordError")

    def test_default_prefers_known_text_column(self) -> None:
        """Default prefers known text column."""
        assert resolve_text_column(["id", "body", "extra"], None) == "body"

    def test_falls_back_to_last_column(self) -> None:
        """Falls back to last column."""
        assert resolve_text_column(["id", "col"], None) == "col"

    def test_empty_headers_raises(self) -> None:
        """An empty header list raises instead of an IndexError."""
        try:
            resolve_text_column([], None)
        except MalformedRecordError:
            return
        raise AssertionError("expected MalformedRecordError")


class TestBuildHelpers:
    """The build helpers produce well-formed documents."""

    def test_build_record_document_normalizes_null_text_to_empty_string(self) -> None:
        """A null field value becomes an empty string, not the literal ``"None"``."""
        opts = ReadOptions()
        doc = build_record_document(
            source=_ref(".csv"),
            decoded=_decoded("row"),
            source_format=SourceFormat.CSV,
            loader_name="csv",
            opts=opts,
            record_index=0,
            record={"body": None},
            source_hash="s",
            title="0",
        )
        assert doc.text == ""

    def test_build_record_document_falls_back_when_title_column_missing(self) -> None:
        """A missing title column value falls back to the caller's title."""
        opts = ReadOptions(title_column="name")
        doc = build_record_document(
            source=_ref(".csv"),
            decoded=_decoded("row"),
            source_format=SourceFormat.CSV,
            loader_name="csv",
            opts=opts,
            record_index=0,
            record={"body": "text"},
            source_hash="s",
            title="0",
        )
        assert doc.title == "0"

    def test_build_record_document_rejects_missing_id_column_value(self) -> None:
        """A configured id column that is absent from the record raises."""
        opts = ReadOptions(id_column="id")
        try:
            build_record_document(
                source=_ref(".csv"),
                decoded=_decoded("row"),
                source_format=SourceFormat.CSV,
                loader_name="csv",
                opts=opts,
                record_index=0,
                record={"body": "text"},
                source_hash="s",
                title="0",
            )
        except MalformedRecordError:
            return
        raise AssertionError("expected MalformedRecordError")

    def test_build_record_document_rejects_null_id_column_value(self) -> None:
        """A configured id column with a null value raises, instead of colliding IDs."""
        opts = ReadOptions(id_column="id")
        try:
            build_record_document(
                source=_ref(".csv"),
                decoded=_decoded("row"),
                source_format=SourceFormat.CSV,
                loader_name="csv",
                opts=opts,
                record_index=0,
                record={"id": None, "body": "text"},
                source_hash="s",
                title="0",
            )
        except MalformedRecordError:
            return
        raise AssertionError("expected MalformedRecordError")


class TestParagraphUnits:
    """Blank lines end a paragraph whatever the line ending."""

    @pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
    def test_blank_lines_split_paragraphs(self, ending: str) -> None:
        """CRLF and CR blank lines split like LF ones."""
        text = ending.join(["first", "", "second", "", ""])

        units = paragraph_units(text)

        assert [u.text for u in units] == ["first", "second"]
