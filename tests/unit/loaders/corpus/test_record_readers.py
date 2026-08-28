"""Tests for the record readers: CSV, TSV, JSON Lines, and JSON."""

from io import BytesIO

from agrag.common.data_models.document import DocumentFamily, SourceFormat
from agrag.loaders.corpus.errors import DocumentTooLargeError, MalformedRecordError
from agrag.loaders.corpus.readers.records import CsvLoader, JsonlLoader, JsonLoader
from agrag.loaders.corpus.types import CsvMode, JsonMode, ReadOptions, SourceRef


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

    def test_one_document_per_row(self) -> None:
        """One document per row."""
        docs = _docs(CsvLoader(), "sample.csv", ".csv")
        assert len(docs) == 3
        assert docs[0].family == DocumentFamily.RECORD
        assert docs[0].source_format == SourceFormat.CSV
        assert docs[0].text == "First row body text."

    def test_rows_have_unique_ids(self) -> None:
        """Each row gets its own id; rows must not share the file-level hash."""
        docs = _docs(CsvLoader(), "sample.csv", ".csv")
        assert len({d.id for d in docs}) == len(docs)

    def test_record_index_increases(self) -> None:
        """Record index increases."""
        docs = _docs(CsvLoader(), "sample.csv", ".csv")
        assert [d.record_index for d in docs] == [0, 1, 2]

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

    def test_missing_id_column_value_raises(self) -> None:
        """Missing id column value raises."""
        ref = SourceRef(uri="x.csv", extension=".csv", byte_size=None)
        source = b"id,body\n,first\n"
        try:
            list(CsvLoader().load(ref, BytesIO(source), ReadOptions(id_column="id")))
        except MalformedRecordError:
            return
        raise AssertionError("expected MalformedRecordError")

    def test_oversized_source_with_unknown_byte_size_raises(self) -> None:
        """A record source with no reported byte size is still capped."""
        ref = SourceRef(uri="x.csv", extension=".csv", byte_size=None)
        source = b"id,body\n" + b"1,x\n" * 20
        try:
            list(
                CsvLoader().load(
                    ref, BytesIO(source), ReadOptions(max_document_bytes=10)
                )
            )
        except DocumentTooLargeError:
            return
        raise AssertionError("expected DocumentTooLargeError")

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

    def test_one_document_per_line(self) -> None:
        """One document per line."""
        docs = _docs(JsonlLoader(), "sample.jsonl", ".jsonl")
        assert len(docs) == 3
        assert docs[0].text == "First jsonl record."

    def test_non_object_line_is_prose(self) -> None:
        """Non object line is prose."""
        ref = SourceRef(uri="x.jsonl", extension=".jsonl", byte_size=None)
        source = b'{"id": "a", "body": "ok"}\n"just a string"\n'
        docs = list(JsonlLoader().load(ref, BytesIO(source), ReadOptions()))
        assert docs[0].family == DocumentFamily.RECORD
        assert docs[1].family == DocumentFamily.PROSE

    def test_malformed_line_raises(self) -> None:
        """Malformed line raises."""
        ref = SourceRef(uri="x.jsonl", extension=".jsonl", byte_size=None)
        source = b'{"id": "a"}\nnot json\n'
        try:
            list(JsonlLoader().load(ref, BytesIO(source), ReadOptions()))
        except MalformedRecordError:
            return
        raise AssertionError("expected MalformedRecordError")

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


class TestJsonLoader:
    """JSON files disambiguate arrays from objects."""

    def test_top_level_array_yields_records(self) -> None:
        """Top level array yields records."""
        docs = _docs(JsonLoader(), "sample_array.json", ".json")
        assert len(docs) == 3
        assert docs[0].family == DocumentFamily.RECORD
        assert docs[0].text == "First array record."

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
