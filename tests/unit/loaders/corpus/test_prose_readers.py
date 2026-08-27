"""Tests for the prose readers: text, Markdown, and AsciiDoc."""

from io import BytesIO

from agrag.common.data_models.document import DocumentFamily, SourceFormat
from agrag.loaders.corpus.errors import DocumentTooLargeError
from agrag.loaders.corpus.readers.prose import (
    AsciiDocLoader,
    MarkdownLoader,
    TextLoader,
)
from agrag.loaders.corpus.types import ReadOptions, SourceRef


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


class TestMarkdownLoader:
    """Markdown files record a heading outline and a title."""

    def test_records_heading_outline(self) -> None:
        """Records heading outline."""
        docs = _documents(MarkdownLoader(), "sample.md", ".md")
        doc = docs[0]
        assert doc.source_format == SourceFormat.MARKDOWN
        assert doc.heading_outline
        levels = [h.level for h in doc.heading_outline]
        assert levels == [1, 2, 3, 2, 2]
        assert doc.title == "Sample Document"


class TestAsciiDocLoader:
    """AsciiDoc falls back to a regex heading scan without docling."""

    def test_records_heading_outline(self) -> None:
        """Records heading outline."""
        ref = SourceRef(uri="x.adoc", extension=".adoc", byte_size=None)
        source = "= Title\n\nBody.\n\n== Section\n\nMore.\n"
        docs = list(
            AsciiDocLoader().load(ref, BytesIO(source.encode("utf-8")), ReadOptions())
        )
        doc = docs[0]
        assert doc.source_format == SourceFormat.ASCIIDOC
        assert doc.title == "Title"
        assert [h.level for h in doc.heading_outline] == [1, 2]
