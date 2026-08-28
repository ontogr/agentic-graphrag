"""Tests for the shared corpus reader helpers and Document id rules."""

from io import BytesIO

import pytest

from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.loaders.corpus.errors import MalformedRecordError
from agrag.loaders.corpus.readers._common import (
    build_prose_document,
    build_record_document,
    read_within_limit,
    record_source_hash,
    resolve_text_column,
    source_title,
)
from agrag.loaders.corpus.types import DecodedText, ReadOptions, SourceRef


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

    def test_id_from_content_hash(self) -> None:
        """Id from content hash."""
        doc = Document(
            text="x",
            title="t",
            uri="u",
            source_format=SourceFormat.TXT,
            family=DocumentFamily.PROSE,
            content_hash="abc",
            loader_name="text",
            char_count=1,
            line_count=1,
        )
        assert doc.id is not None

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

    def test_build_prose_document_strips_text_when_store_text_false(self) -> None:
        """Build prose document strips text when store text false."""
        doc = build_prose_document(
            source=_ref(".txt"),
            text="secret",
            encoding="utf-8",
            source_format=SourceFormat.TXT,
            loader_name="text",
            opts=ReadOptions(store_text=False),
            title="t",
        )
        assert doc.text == ""

    def test_build_record_document_has_unique_hash_per_text(self) -> None:
        """Build record document has unique hash per text."""
        opts = ReadOptions()
        common = {
            "source": _ref(".csv"),
            "decoded": _decoded("row"),
            "source_format": SourceFormat.CSV,
            "loader_name": "csv",
            "opts": opts,
            "source_hash": "s",
            "title": "0",
        }
        one = build_record_document(record_index=0, record={"body": "alpha"}, **common)
        two = build_record_document(record_index=1, record={"body": "beta"}, **common)
        assert one.id != two.id

    def test_source_title_uses_file_stem(self) -> None:
        """Source title uses file stem."""
        assert source_title(_ref(".csv")) == "file.csv"

    def test_record_source_hash_is_stable(self) -> None:
        """Record source hash is stable."""
        assert record_source_hash(b"abc") == record_source_hash(b"abc")

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

    def test_build_record_document_strips_text_when_store_text_false(self) -> None:
        """Store text false hides text but keeps char_count from the real value."""
        opts = ReadOptions(store_text=False)
        doc = build_record_document(
            source=_ref(".csv"),
            decoded=_decoded("row"),
            source_format=SourceFormat.CSV,
            loader_name="csv",
            opts=opts,
            record_index=0,
            record={"body": "alpha"},
            source_hash="s",
            title="0",
        )
        assert doc.text == ""
        assert doc.char_count == len("alpha")

    def test_build_record_document_uses_title_column(self) -> None:
        """The configured title column overrides the caller's fallback title."""
        opts = ReadOptions(title_column="name")
        doc = build_record_document(
            source=_ref(".csv"),
            decoded=_decoded("row"),
            source_format=SourceFormat.CSV,
            loader_name="csv",
            opts=opts,
            record_index=0,
            record={"name": "Alpha", "body": "text"},
            source_hash="s",
            title="0",
        )
        assert doc.title == "Alpha"

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
