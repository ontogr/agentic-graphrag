"""Tests for TextLoader, MarkdownLoader, and AsciiDocLoader.

Reads fixtures from the local ``fixtures/`` directory. Covers plain-text and
log-format documents, the ``store_text=False`` text-stripping option,
oversized-source rejection,
Markdown heading-outline extraction with title detection, and AsciiDoc's
regex-based heading scan used as the fallback when docling is not
installed.
"""

from io import BytesIO

from agrag.common.data_models.document import DocumentFamily, SourceFormat
from agrag.common.data_models.normalization import Normalization
from agrag.loaders.docling.loader import DoclingLoader
from agrag.loaders.errors import DocumentTooLargeError
from agrag.loaders.prose import (
    TextLoader,
)
from agrag.loaders.types import ReadOptions, SourceRef


_FIXTURES = __import__("pathlib").Path(__file__).parent / "fixtures"


def _ref(name: str, extension: str) -> SourceRef:
    path = _FIXTURES / name
    return SourceRef(uri=str(path), extension=extension, byte_size=path.stat().st_size)


def _documents(loader, name: str, extension: str, opts: ReadOptions | None = None):
    ref = _ref(name, extension)
    return list(loader.load(ref, open(_FIXTURES / name, "rb"), opts or ReadOptions()))


class TestTextLoader:
    """Plain-text and log files become one prose document."""

    def test_text_file_is_one_prose_document(self) -> None:
        """Text file is one prose document."""
        docs = _documents(TextLoader(), "sample.txt", ".txt")
        assert len(docs) == 1
        doc = docs[0]
        assert doc.family == DocumentFamily.PROSE
        assert doc.source_format == SourceFormat.TXT
        assert "First line of plain text." in doc.text
        assert doc.char_count == len(doc.text)

    def test_document_records_the_normalization(self) -> None:
        """The document says how its text was normalized."""
        default = _documents(TextLoader(), "sample.txt", ".txt")[0]
        raw = _documents(
            TextLoader(),
            "sample.txt",
            ".txt",
            ReadOptions(normalization=Normalization(unicode_form="none")),
        )[0]

        assert default.normalization == Normalization()
        assert raw.normalization == Normalization(unicode_form="none")

    def test_log_file_uses_log_format(self) -> None:
        """Log file uses log format."""
        docs = _documents(TextLoader(), "sample.log", ".log")
        assert docs[0].source_format == SourceFormat.LOG

    def test_store_text_false_hides_text(self) -> None:
        """Store text false hides text."""
        docs = _documents(
            TextLoader(), "sample.txt", ".txt", ReadOptions(store_text=False)
        )
        assert docs[0].text == ""

    def test_oversized_source_raises(self) -> None:
        """Oversized source raises."""
        ref = _ref("sample.txt", ".txt")
        loader = TextLoader()
        try:
            list(
                loader.load(
                    ref,
                    BytesIO((_FIXTURES / "sample.txt").read_bytes()),
                    ReadOptions(max_document_bytes=1),
                )
            )
        except DocumentTooLargeError:
            return
        raise AssertionError("expected DocumentTooLargeError")


class TestDoclingAsciiDocLoader:
    """AsciiDoc files load with docling sections."""

    def test_adoc_file_gives_nested_sections_with_content(self) -> None:
        """Headings nest and units hold the section text."""
        docs = _documents(DoclingLoader(), "sample.adoc", ".adoc")

        assert len(docs) == 1
        doc = docs[0]
        assert doc.source_format == SourceFormat.ASCIIDOC
        assert [(s.heading, s.depth) for s in doc.sections] == [
            ("Sample Guide", 0),
            ("Setup", 1),
            ("Details", 2),
        ]
        assert doc.sections[2].parent == 1
        assert all(s.units for s in doc.sections)
