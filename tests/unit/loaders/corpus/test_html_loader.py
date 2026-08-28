"""Tests for the HTML reader."""

from io import BytesIO

from agrag.common.data_models.document import DocumentFamily, SourceFormat
from agrag.loaders.corpus.errors import DocumentTooLargeError
from agrag.loaders.corpus.readers.html import HtmlLoader
from agrag.loaders.corpus.types import ReadOptions, SourceRef


_FIXTURES = __import__("pathlib").Path(__file__).parent / "fixtures"


class TestHtmlLoader:
    """The HTML reader keeps the main content and drops navigation."""

    def test_keeps_main_content(self) -> None:
        """Keeps main content."""
        ref = SourceRef(
            uri=str(_FIXTURES / "sample.html"), extension=".html", byte_size=None
        )
        docs = list(
            HtmlLoader().load(
                ref,
                BytesIO((_FIXTURES / "sample.html").read_bytes()),
                ReadOptions(),
            )
        )
        doc = docs[0]
        assert doc.source_format == SourceFormat.HTML
        assert doc.family == DocumentFamily.PROSE
        assert "main article content" in doc.text
        assert "Home" not in doc.text

    def test_custom_selector_overrides_default(self) -> None:
        """Custom selector overrides default."""
        ref = SourceRef(uri="x.html", extension=".html", byte_size=None)
        source = "<body><nav>NAV</nav><div id='x'>PICKED</div></body>"
        docs = list(
            HtmlLoader().load(
                ref, BytesIO(source.encode("utf-8")), ReadOptions(html_selector="#x")
            )
        )
        assert "PICKED" in docs[0].text
        assert "NAV" not in docs[0].text

    def test_oversized_source_with_unknown_byte_size_raises(self) -> None:
        """A source with no reported byte size is still capped, not fully buffered."""
        ref = SourceRef(uri="x.html", extension=".html", byte_size=None)
        source = b"<body>" + b"a" * 100 + b"</body>"
        try:
            list(
                HtmlLoader().load(
                    ref, BytesIO(source), ReadOptions(max_document_bytes=10)
                )
            )
        except DocumentTooLargeError:
            return
        raise AssertionError("expected DocumentTooLargeError")
