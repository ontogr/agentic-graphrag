"""Tests for default loader precedence.

Docling reads every rich format and the core readers keep plain text, XML and the
record formats. PDF and image files need the ``docling`` extra, and the registry
says so when that extra is missing.
"""

import importlib.util
from unittest.mock import patch

import pytest

from agrag.loaders import registry
from agrag.loaders.defaults import register_default_loaders
from agrag.loaders.docling.loader import DoclingLoader, DoclingPdfLoader
from agrag.loaders.errors import MissingExtraError
from agrag.loaders.loader_registry import LoaderRegistry
from agrag.loaders.prose import TextLoader, XmlLoader
from agrag.loaders.records import CsvLoader, JsonlLoader, JsonLoader
from agrag.loaders.types import SourceRef


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

    def test_a_missing_model_package_fails_pdf_even_when_docling_is_installed(
        self,
    ) -> None:
        """The core docling package does not satisfy the PDF extra."""
        pytest.importorskip("docling")
        real_find_spec = importlib.util.find_spec

        def _find_spec(name: str, *args: object, **kwargs: object) -> object:
            if name == "docling_ibm_models":
                return None
            return real_find_spec(name, *args, **kwargs)

        with (
            patch("importlib.util.find_spec", side_effect=_find_spec),
            pytest.raises(MissingExtraError) as error,
        ):
            _loader_for(".pdf")

        assert error.value.extra == "docling"
        assert type(_loader_for(".md")) is DoclingLoader

    def test_the_rich_formats_do_not_need_the_models(self) -> None:
        """A bare install still reads Markdown."""
        pytest.importorskip("docling")
        with patch("importlib.util.find_spec", return_value=None):
            loader = _loader_for(".md")

        assert type(loader) is DoclingLoader


class TestRegisterDefaultLoaders:
    """A fresh registry gets the same loaders as the default registry."""

    def test_fresh_registry_routes_rich_and_core_formats(self) -> None:
        """Both docling and core loaders are present after one call."""
        fresh = LoaderRegistry()
        register_default_loaders(fresh)

        assert (
            type(fresh.for_source(SourceRef(uri="x.txt", extension=".txt")))
            is TextLoader
        )
        assert (
            type(fresh.for_source(SourceRef(uri="x.md", extension=".md")))
            is DoclingLoader
        )

    def test_registering_twice_keeps_one_loader_per_extension(self) -> None:
        """A second call does not add a duplicate registration."""
        fresh = LoaderRegistry()
        register_default_loaders(fresh)
        register_default_loaders(fresh)

        assert (
            type(fresh.for_source(SourceRef(uri="x.csv", extension=".csv")))
            is CsvLoader
        )
