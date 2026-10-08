"""Tests for the OCR choice and the converter cache."""

import io
from pathlib import Path

import pytest

from agrag.loaders.docling._converters import ocr_choice, pdf_converter, slim_converter


pdfium = pytest.importorskip("pypdfium2")
pytest.importorskip("docling")
Image = pytest.importorskip("PIL.Image")

TEXT_PDF = (Path(__file__).parent / "fixtures" / "with_text.pdf").read_bytes()


def _scanned_page() -> bytes:
    """Return a one-page PDF that holds an image and no text."""
    buffer = io.BytesIO()
    Image.new("RGB", (200, 200), "white").save(buffer, format="PDF")
    return buffer.getvalue()


def _join(*files: bytes) -> bytes:
    """Return one PDF with the pages of all the files, in order."""
    merged = pdfium.PdfDocument.new()
    for raw in files:
        merged.import_pages(pdfium.PdfDocument(raw))
    buffer = io.BytesIO()
    merged.save(buffer)
    return buffer.getvalue()


class TestOcrChoice:
    """The choice follows how many pages lack a text layer."""

    def test_text_on_every_page_needs_no_ocr(self) -> None:
        """No page lacks text."""
        assert ocr_choice(TEXT_PDF) == "off"

    def test_no_text_on_any_page_means_full_page_ocr(self) -> None:
        """A scan is OCRed whole."""
        assert ocr_choice(_scanned_page()) == "full"

    def test_a_mix_means_ocr_of_the_regions_without_text(self) -> None:
        """One page of three lacks text."""
        mixed = _join(TEXT_PDF, _scanned_page())

        assert ocr_choice(mixed) == "default"

    def test_four_scanned_pages_for_each_text_page_means_full_page_ocr(self) -> None:
        """The line is 80% of the pages without text."""
        text_pages = len(pdfium.PdfDocument(TEXT_PDF))
        scanned = [_scanned_page()] * (4 * text_pages)

        assert ocr_choice(_join(TEXT_PDF, *scanned)) == "full"

    def test_just_under_the_line_means_ocr_of_the_regions_without_text(self) -> None:
        """Three scanned pages for each text page is 75%."""
        text_pages = len(pdfium.PdfDocument(TEXT_PDF))
        scanned = [_scanned_page()] * (3 * text_pages)

        assert ocr_choice(_join(TEXT_PDF, *scanned)) == "default"


class TestConverterCache:
    """Each converter is built once and reused."""

    def test_the_same_converter_comes_back_for_the_same_choice(self) -> None:
        """Models load once per process."""
        assert slim_converter() is slim_converter()
        assert pdf_converter("off") is pdf_converter("off")

    def test_each_ocr_choice_has_its_own_converter(self) -> None:
        """The OCR setting is part of the pipeline options."""
        assert pdf_converter("off") is not pdf_converter("full")
