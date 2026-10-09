"""Build and reuse the Docling converters.

A converter loads its models once, so each one is built on first use under a lock
and kept for the life of the process. Tests can drop them with
``clear_converters``.
"""

import threading
from typing import Any, Literal


OcrChoice = Literal["off", "default", "full"]

# A page with less text than a short sentence has no usable text layer.
_TEXT_LAYER_MIN_CHARS = 50
# Past this share of pages without text, whole-page OCR is cheaper than regions.
_FULL_PAGE_OCR_SHARE = 0.8

_converters: dict[str | None, Any] = {}
_converters_lock = threading.Lock()


def slim_converter() -> Any:
    """Return the converter for formats that need no model."""
    with _converters_lock:
        converter = _converters.get(None)
        if converter is None:
            from docling.document_converter import DocumentConverter  # noqa: PLC0415

            converter = DocumentConverter()
            _converters[None] = converter
        return converter


def pdf_converter(ocr: OcrChoice) -> Any:
    """Return the converter for PDF and image files with one OCR choice.

    Tables use the fast mode. Headings take their depth from the PDF bookmarks.

    Args:
        ocr: ``"off"`` for no OCR, ``"default"`` to OCR only the regions that have no
            text layer, or ``"full"`` to OCR every page.
    """
    with _converters_lock:
        converter = _converters.get(ocr)
        if converter is None:
            converter = _build_pdf_converter(ocr)
            _converters[ocr] = converter
        return converter


def clear_converters() -> None:
    """Drop the cached converters, so tests can rebuild them."""
    with _converters_lock:
        _converters.clear()


def _build_pdf_converter(ocr: OcrChoice) -> Any:
    """Build the converter for PDF and image files with one OCR choice."""
    from docling.datamodel.base_models import InputFormat  # noqa: PLC0415
    from docling.datamodel.pipeline_options import (  # noqa: PLC0415
        HeadingHierarchyOptions,
        OcrMode,
        PdfPipelineOptions,
        TableFormerMode,
        TableStructureOptions,
    )
    from docling.document_converter import (  # noqa: PLC0415
        DocumentConverter,
        ImageFormatOption,
        PdfFormatOption,
    )

    options = PdfPipelineOptions(
        do_ocr=ocr != "off",
        do_table_structure=True,
        table_structure_options=TableStructureOptions(mode=TableFormerMode.FAST),
    )
    if ocr != "off":
        options.ocr_options.mode = (
            OcrMode.FULL_PAGE if ocr == "full" else OcrMode.DEFAULT
        )
    options.heading_hierarchy_options = HeadingHierarchyOptions(
        enabled=True, use_bookmarks=True, use_numbering=False, use_style=False
    )
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=options),
            InputFormat.IMAGE: ImageFormatOption(pipeline_options=options),
        }
    )


def ocr_choice(pdf: bytes) -> OcrChoice:
    """Choose how to OCR a PDF from the text layer of its pages.

    A page with fewer than 50 characters of text counts as having no text layer.

    Args:
        pdf: The PDF file bytes.

    Returns:
        ``"off"`` when every page has text, ``"full"`` when at least 80% of the pages
        have none, and ``"default"`` otherwise.
    """
    import pypdfium2  # noqa: PLC0415

    document = pypdfium2.PdfDocument(pdf)
    try:
        pages = len(document)
        if pages == 0:
            return "off"
        lacking = sum(
            len(document[i].get_textpage().get_text_range().strip())
            < _TEXT_LAYER_MIN_CHARS
            for i in range(pages)
        )
    finally:
        document.close()
    if lacking == 0:
        return "off"
    return "full" if lacking / pages >= _FULL_PAGE_OCR_SHARE else "default"
