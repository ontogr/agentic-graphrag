"""Tests for default loader precedence between core readers and docling.

Verifies core loaders (csv, markdown, html) win over docling's registrations
for their formats, docling wins for formats with no core loader (pdf, xml)
and for AsciiDoc's structural parser when docling is installed, and that the
regex-based AsciiDocLoader is used as a fallback on an isolated
LoaderRegistry when docling is absent. Docling-dependent tests use
``pytest.importorskip("docling")``.
"""

import pytest

import agrag.loaders.docling  # noqa: F401  (registers the docling loaders)
from agrag.loaders.corpus import registry
from agrag.loaders.corpus.readers.html import HtmlLoader
from agrag.loaders.corpus.readers.prose import AsciiDocLoader, MarkdownLoader
from agrag.loaders.corpus.readers.records import CsvLoader
from agrag.loaders.corpus.registry import LoaderRegistry
from agrag.loaders.corpus.types import SourceRef
from agrag.loaders.docling.loader import DoclingLoader  # noqa: PLC0415


class TestCorpusRegistration:
    """Verify default loader precedence between core readers and docling."""

    def test_core_loader_wins_for_csv(self) -> None:
        """Core loader wins for csv."""
        loader = registry.for_source(SourceRef(uri="x.csv", extension=".csv"))
        assert isinstance(loader, CsvLoader)

    def test_core_loader_wins_for_markdown(self) -> None:
        """Core loader wins for markdown."""
        loader = registry.for_source(SourceRef(uri="x.md", extension=".md"))
        assert isinstance(loader, MarkdownLoader)

    def test_core_loader_wins_for_html(self) -> None:
        """Core loader wins for html."""
        loader = registry.for_source(SourceRef(uri="x.html", extension=".html"))
        assert isinstance(loader, HtmlLoader)

    def test_docling_wins_for_asciidoc(self) -> None:
        """Docling's structural AsciiDoc parser is preferred over the regex fallback."""
        pytest.importorskip("docling")
        for extension in (".adoc", ".asciidoc"):
            loader = registry.for_source(
                SourceRef(uri=f"x{extension}", extension=extension)
            )
            assert isinstance(loader, DoclingLoader)

    def test_core_asciidoc_is_the_fallback_when_docling_is_not_registered(self) -> None:
        """The regex AsciiDoc reader is used when docling is not installed."""
        isolated_registry = LoaderRegistry()
        isolated_registry.register(AsciiDocLoader(), prefer=True)
        loader = isolated_registry.for_source(
            SourceRef(uri="x.adoc", extension=".adoc")
        )
        assert isinstance(loader, AsciiDocLoader)

    def test_docling_wins_for_pdf(self) -> None:
        """PDF has no core loader, so docling resolves as the default."""
        pytest.importorskip("docling")
        loader = registry.for_source(SourceRef(uri="x.pdf", extension=".pdf"))
        assert isinstance(loader, DoclingLoader)

    def test_docling_wins_for_xml(self) -> None:
        """XML has no core loader, so docling resolves as the default."""
        pytest.importorskip("docling")
        loader = registry.for_source(SourceRef(uri="x.xml", extension=".xml"))
        assert isinstance(loader, DoclingLoader)
