"""Tests for CsvLoader, JsonlLoader, and JsonLoader.

Reads fixtures from the local ``fixtures/`` directory. Covers per-row/line/
element document splitting, resume via start_at (including JSON Lines counting
logical records rather than physical lines across blank lines), id/title/text
column configuration, CSV table mode producing a single prose document, TSV
delimiter handling, storing raw records, hiding text under ``store_text=False``,
JSON array-versus-object disambiguation and DOCUMENT mode, and malformed input
raising MalformedRecordError (missing/empty text or id column, unterminated CSV
quoting).
"""

from datetime import date
from io import BytesIO

import pytest

from agrag.common.data_models.document import DocumentFamily
from agrag.loaders.errors import MalformedRecordError
from agrag.loaders.records import CsvLoader, JsonlLoader, JsonLoader
from agrag.loaders.types import CsvMode, JsonMode, ReadOptions, SourceRef


_FIXTURES = __import__("pathlib").Path(__file__).parent / "fixtures"


def _ref(name: str, extension: str) -> SourceRef:
    path = _FIXTURES / name
    return SourceRef(uri=str(path), extension=extension, byte_size=path.stat().st_size)


def _docs(loader, name: str, extension: str, opts: ReadOptions | None = None):
    return list(
        loader.load(
            _ref(name, extension), open(_FIXTURES / name, "rb"), opts or ReadOptions()
        )
    )


class TestCsvLoader:
    """CSV files yield one record document per row."""

    def test_id_column_sets_record_id(self) -> None:
        """Id column sets record id."""
        docs = _docs(CsvLoader(), "sample.csv", ".csv", ReadOptions(id_column="id"))
        assert [d.record_id for d in docs] == ["1", "2", "3"]
        assert docs[0].id is not None

    def test_resume_skips_rows_before_start_at(self) -> None:
        """Resume skips rows before start at."""
        ref = _ref("sample.csv", ".csv")
        docs = list(
            CsvLoader().load(
                ref,
                BytesIO((_FIXTURES / "sample.csv").read_bytes()),
                ReadOptions(),
                start_at=1,
            )
        )
        assert [d.record_index for d in docs] == [1, 2]

    def test_table_mode_yields_one_prose_document(self) -> None:
        """Table mode yields one prose document."""
        docs = _docs(
            CsvLoader(), "sample.csv", ".csv", ReadOptions(csv_mode=CsvMode.TABLE)
        )
        assert len(docs) == 1
        assert docs[0].family == DocumentFamily.PROSE

    def test_tsv_uses_tab_delimiter(self) -> None:
        """Tsv uses tab delimiter."""
        ref = SourceRef(uri="x.tsv", extension=".tsv", byte_size=None)
        source = b"id\tbody\n1\tfirst\n2\tsecond\n"
        docs = list(CsvLoader().load(ref, BytesIO(source), ReadOptions()))
        assert len(docs) == 2
        assert docs[0].text == "first"

    def test_missing_text_column_raises(self) -> None:
        """Missing text column raises."""
        try:
            _docs(CsvLoader(), "sample.csv", ".csv", ReadOptions(text_column="missing"))
        except MalformedRecordError:
            return
        raise AssertionError("expected MalformedRecordError")

    def test_store_raw_record_keeps_row(self) -> None:
        """Store raw record keeps row."""
        docs = _docs(
            CsvLoader(), "sample.csv", ".csv", ReadOptions(store_raw_record=True)
        )
        assert docs[0].raw_record == {"id": "1", "body": "First row body text."}

    def test_store_text_false_hides_text(self) -> None:
        """Store text false hides text."""
        docs = _docs(CsvLoader(), "sample.csv", ".csv", ReadOptions(store_text=False))
        assert docs[0].text == ""
        assert docs[0].char_count == len("First row body text.")

    def test_title_column_sets_title(self) -> None:
        """Title column sets title."""
        docs = _docs(CsvLoader(), "sample.csv", ".csv", ReadOptions(title_column="id"))
        assert [d.title for d in docs] == ["1", "2", "3"]

    def test_date_columns_set_independent_dates(self) -> None:
        """Date columns parse ISO dates and date-times into their date parts."""
        ref = SourceRef(uri="x.csv", extension=".csv", byte_size=None)
        source = b"body,published,about\ntext,2024-05-01,2023-12-31T08:00:00\n"

        [document] = list(
            CsvLoader().load(
                ref,
                BytesIO(source),
                ReadOptions(
                    text_column="body",
                    published_at_column="published",
                    content_date_column="about",
                ),
            )
        )

        assert document.published_at == date(2024, 5, 1)
        assert document.content_date == date(2023, 12, 31)

    @pytest.mark.parametrize(
        "source",
        [b"body,published\ntext,\n", b"body,published\ntext,   \n"],
    )
    def test_blank_date_values_give_none(self, source: bytes) -> None:
        """Blank date cells produce no date."""
        ref = SourceRef(uri="x.csv", extension=".csv", byte_size=None)

        [document] = list(
            CsvLoader().load(
                ref,
                BytesIO(source),
                ReadOptions(published_at_column="published"),
            )
        )

        assert document.published_at is None

    def test_missing_date_column_gives_none(self) -> None:
        """An absent optional date column produces no date."""
        ref = SourceRef(uri="x.csv", extension=".csv", byte_size=None)

        [document] = list(
            CsvLoader().load(
                ref,
                BytesIO(b"body\ntext\n"),
                ReadOptions(published_at_column="published"),
            )
        )

        assert document.published_at is None

    def test_invalid_date_names_column_and_source(self) -> None:
        """Malformed date values identify the configured column and source."""
        ref = SourceRef(uri="x.csv", extension=".csv", byte_size=None)
        options = ReadOptions(published_at_column="published")

        with pytest.raises(MalformedRecordError, match="published.*x\\.csv"):
            list(
                CsvLoader().load(
                    ref,
                    BytesIO(b"body,published\ntext,last week\n"),
                    options,
                )
            )

    def test_missing_id_column_value_raises(self) -> None:
        """Missing id column value raises."""
        ref = SourceRef(uri="x.csv", extension=".csv", byte_size=None)
        source = b"id,body\n,first\n"
        try:
            list(CsvLoader().load(ref, BytesIO(source), ReadOptions(id_column="id")))
        except MalformedRecordError:
            return
        raise AssertionError("expected MalformedRecordError")

    def test_malformed_quoting_raises(self) -> None:
        """An unterminated quoted field raises instead of ingesting garbled data."""
        ref = SourceRef(uri="x.csv", extension=".csv", byte_size=None)
        source = b'id,body\n1,"unterminated\n2,ok\n'
        try:
            list(CsvLoader().load(ref, BytesIO(source), ReadOptions()))
        except MalformedRecordError:
            return
        raise AssertionError("expected MalformedRecordError")


class TestJsonlLoader:
    """JSON Lines files yield one document per line."""

    def test_non_object_line_is_prose(self) -> None:
        """Non object line is prose."""
        ref = SourceRef(uri="x.jsonl", extension=".jsonl", byte_size=None)
        source = b'{"id": "a", "body": "ok"}\n"just a string"\n'
        docs = list(JsonlLoader().load(ref, BytesIO(source), ReadOptions()))
        assert docs[0].family == DocumentFamily.RECORD
        assert docs[1].family == DocumentFamily.PROSE

    def test_blank_lines_do_not_shift_record_index(self) -> None:
        """Record index counts emitted records, skipping blank physical lines."""
        ref = SourceRef(uri="x.jsonl", extension=".jsonl", byte_size=None)
        source = b'{"body": "one"}\n\n{"body": "two"}\n\n{"body": "three"}\n'
        docs = list(JsonlLoader().load(ref, BytesIO(source), ReadOptions()))
        assert [d.record_index for d in docs] == [0, 1, 2]

    def test_resume_after_blank_line_uses_record_count_not_line_number(self) -> None:
        """Resuming with start_at counts logical records, not physical lines."""
        ref = SourceRef(uri="x.jsonl", extension=".jsonl", byte_size=None)
        source = b'{"body": "one"}\n\n{"body": "two"}\n\n{"body": "three"}\n'
        docs = list(JsonlLoader().load(ref, BytesIO(source), ReadOptions(), start_at=1))
        assert [d.record_index for d in docs] == [1, 2]
        assert docs[0].text == "two"

    def test_null_date_value_gives_none(self) -> None:
        """A JSON null date value produces no date."""
        ref = SourceRef(uri="x.jsonl", extension=".jsonl", byte_size=None)

        [document] = list(
            JsonlLoader().load(
                ref,
                BytesIO(b'{"body": "text", "published": null}\n'),
                ReadOptions(published_at_column="published"),
            )
        )

        assert document.published_at is None


class TestJsonLoader:
    """JSON files disambiguate arrays from objects."""

    def test_top_level_object_is_one_prose_document(self) -> None:
        """Top level object is one prose document."""
        docs = _docs(JsonLoader(), "sample_object.json", ".json")
        assert len(docs) == 1
        assert docs[0].family == DocumentFamily.PROSE

    def test_document_mode_keeps_array_as_one_document(self) -> None:
        """Document mode keeps array as one document."""
        docs = _docs(
            JsonLoader(),
            "sample_array.json",
            ".json",
            ReadOptions(json_mode=JsonMode.DOCUMENT),
        )
        assert len(docs) == 1

    def test_resume_skips_elements_before_start_at(self) -> None:
        """Resume skips elements before start at."""
        ref = _ref("sample_array.json", ".json")
        docs = list(
            JsonLoader().load(
                ref,
                BytesIO((_FIXTURES / "sample_array.json").read_bytes()),
                ReadOptions(),
                start_at=2,
            )
        )
        assert [d.record_index for d in docs] == [2]
