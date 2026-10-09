import threading
from typing import Any, Literal


OcrChoice = Literal["off", "default", "full"]
_SlimKey = Literal["slim"]

# A page with a real text layer has far more than a few stray characters such as a
# page number, so fewer characters than this means the page needs OCR.
_TEXT_LAYER_MIN_CHARS = 50
# When most pages lack text the file is a scan, so every page gets full-page OCR
# rather than OCR of only the text-free gaps.
_FULL_PAGE_OCR_SHARE = 0.8

_converters: dict[_SlimKey | OcrChoice, Any] = {}
_converters_lock = threading.Lock()


def slim_converter() -> Any:
    with _converters_lock:
        converter = _converters.get("slim")
        if converter is None:
            from docling.document_converter import DocumentConverter  # noqa: PLC0415

            converter = DocumentConverter()
            _converters["slim"] = converter
        return converter


def pdf_converter(ocr: OcrChoice) -> Any:
    with _converters_lock:
        converter = _converters.get(ocr)
        if converter is None:
            converter = _build_pdf_converter(ocr)
            _converters[ocr] = converter
        return converter


def clear_converters() -> None:
    with _converters_lock:
        _converters.clear()


def _build_pdf_converter(ocr: OcrChoice) -> Any:
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
