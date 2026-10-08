"""Tests for default loader precedence.

Docling reads every rich format and the core readers keep plain text, XML and the
record formats. PDF and image files need the ``docling`` extra, and the registry
says so when the models are missing.
"""

from unittest.mock import patch

import pytest

import agrag.loaders.docling  # noqa: F401  (registers the docling loaders)
from agrag.loaders.corpus import registry
from agrag.loaders.corpus.errors import MissingExtraError
from agrag.loaders.corpus.readers.prose import TextLoader, XmlLoader
from agrag.loaders.corpus.readers.records import CsvLoader, JsonlLoader, JsonLoader
from agrag.loaders.corpus.types import SourceRef
from agrag.loaders.docling.loader import DoclingLoader, DoclingPdfLoader


def _loader_for(extension: str) -> object:
    return registry.for_source(SourceRef(uri="x" + extension, extension=extension))


class TestCorpusRegistration:
    """Each extension goes to the loader that the design names."""

    @pytest.mark.parametrize(
        ("extension", "expected"),
        [
            (".txt", TextLoader),
            (".log", TextLoader),
            (".xml", XmlLoader),
            (".csv", CsvLoader),
            (".tsv", CsvLoader),
            (".jsonl", JsonlLoader),
            (".json", JsonLoader),
        ],
    )
    def test_core_readers_keep_text_xml_and_records(
        self, extension: str, expected: type
    ) -> None:
        """Rows keep their identity, so Docling never reads them."""
        assert type(_loader_for(extension)) is expected

    @pytest.mark.parametrize(
        "extension",
        [".md", ".markdown", ".html", ".htm", ".adoc", ".asciidoc"]
        + [".docx", ".pptx", ".xlsx"],
    )
    def test_docling_reads_the_rich_formats(self, extension: str) -> None:
        """These formats need no extra."""
        pytest.importorskip("docling")

        assert type(_loader_for(extension)) is DoclingLoader

    @pytest.mark.parametrize("extension", [".pdf", ".png", ".jpg", ".tiff"])
    def test_docling_pdf_reads_pdf_and_images(self, extension: str) -> None:
        """PDF and images use the loader that needs the models."""
        pytest.importorskip("docling_ibm_models")

        assert type(_loader_for(extension)) is DoclingPdfLoader


class TestMissingExtra:
    """A PDF without the models gives an error that names the extra."""

    def test_pdf_without_the_models_names_the_extra(self) -> None:
        """The check looks for the module that only the extra installs."""
        with (
            patch("importlib.util.find_spec", return_value=None),
            pytest.raises(MissingExtraError) as error,
        ):
            _loader_for(".pdf")

        assert error.value.extra == "docling"
        assert "agentic-graphrag[docling]" in str(error.value)

    def test_the_rich_formats_do_not_need_the_models(self) -> None:
        """A bare install still reads Markdown."""
        pytest.importorskip("docling")
        with patch("importlib.util.find_spec", return_value=None):
            loader = _loader_for(".md")

        assert type(loader) is DoclingLoader
