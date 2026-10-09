"""Docling-backed loaders.

``DoclingLoader`` reads the formats that need no model: Markdown, HTML, AsciiDoc, DOCX,
PPTX and XLSX. ``DoclingPdfLoader`` reads PDF and image files and needs the ``docling``
extra. Importing this module does not import the docling library: the loaders import
it when they convert.
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Iterator
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Any, BinaryIO


if TYPE_CHECKING:
    from docling_core.types.doc import DoclingDocument

from agrag.common.data_models.document import Document, SourceFormat
from agrag.loaders.base import ProseLoader
from agrag.loaders.common import (
    build_prose_document,
    read_within_limit,
    source_title,
)
from agrag.loaders.docling._converters import ocr_choice, pdf_converter, slim_converter
from agrag.loaders.docling._sections import (
    DocumentBody,
    numbered_depths,
    read_body,
    sections_from_docling,
)
from agrag.loaders.errors import DocumentConversionError, MissingExtraError
from agrag.loaders.types import ReadOptions, SourceRef


class DoclingLoader(ProseLoader):
    """Reads Markdown, HTML, AsciiDoc, DOCX, PPTX and XLSX files with docling.

    The loader gives a document its sections from the structure that docling finds. It
    needs no model and no extra. The content hash comes from the raw source bytes,
    because the parsed output can change between docling versions and runs.

    Attributes:
        extensions: The formats this loader reads.
    """

    _formats: dict[str, SourceFormat] = {
        ".md": SourceFormat.MARKDOWN,
        ".markdown": SourceFormat.MARKDOWN,
        ".html": SourceFormat.HTML,
        ".htm": SourceFormat.HTML,
        ".adoc": SourceFormat.ASCIIDOC,
        ".asciidoc": SourceFormat.ASCIIDOC,
        ".docx": SourceFormat.DOCX,
        ".pptx": SourceFormat.PPTX,
        ".xlsx": SourceFormat.XLSX,
    }
    extensions = frozenset(_formats)

    def load(
        self,
        source: SourceRef,
        stream: BinaryIO,
        opts: ReadOptions,
        *,
        start_at: int = 0,
    ) -> Iterator[Document]:
        """Yield one prose Document parsed by docling.

        Args:
            source: The source to read.
            stream: The open binary stream for the source.
            opts: The read options.
            start_at: Ignored by prose loaders.

        Yields:
            One Document. When ``opts.store_text`` is on, its text is the docling
            Markdown export and its sections hold the content; with the flag off
            both are empty. Its title is the first heading, or the file name when
            the source has no heading.

        Raises:
            DocumentTooLargeError: The source is larger than the configured byte
                limit.
            MissingExtraError: ``DoclingPdfLoader`` only. A package that docling
                needs is not installed, and the error names the ``docling`` extra.
                It is an ``UnsupportedFormatError``, so SKIP and QUARANTINE treat
                it like an unsupported format.
            ImportError: ``DoclingLoader`` only. A package that docling needs is
                not installed. This is an install problem, not a problem with the
                source, so the walker policies do not catch it.
            DocumentConversionError: Docling or its export failed on the source,
                for any other reason. Walker policies such as SKIP and QUARANTINE
                catch this error.
            ValueError: ``opts.max_document_bytes`` is not a positive integer.
        """
        raw = read_within_limit(stream, source, opts)
        try:
            parsed = self._convert(source, raw)
            text = parsed.export_to_markdown()
        except Exception as exc:
            if isinstance(exc, ImportError):
                if self.extra is None:
                    raise
                raise MissingExtraError(source.extension, self.extra) from exc
            raise DocumentConversionError(
                f"docling could not convert {source.uri}: {exc}"
            ) from exc
        body = read_body(parsed)
        sections = sections_from_docling(body, self._heading_depths(body))
        try:
            loader_version: str | None = version("docling")
        except PackageNotFoundError:
            try:
                loader_version = version("docling-slim")
            except PackageNotFoundError:
                loader_version = None
        title = next((s.heading for s in sections if s.heading), None)
        yield build_prose_document(
            source=source,
            text=text,
            encoding="utf-8",
            source_format=self._formats[source.extension],
            loader_name="docling",
            opts=opts,
            title=title or source_title(source),
            sections=sections,
            content_hash=hashlib.sha256(raw).hexdigest(),
            loader_version=loader_version,
        )

    def _convert(self, source: SourceRef, raw: bytes) -> DoclingDocument:
        from docling.datamodel.base_models import DocumentStream  # noqa: PLC0415

        stream = DocumentStream(name=source.uri, stream=io.BytesIO(raw))
        return self._converter(source, raw).convert(stream).document

    def _converter(self, source: SourceRef, raw: bytes) -> Any:
        """Return the docling converter that reads this source."""
        return slim_converter()

    def _heading_depths(self, body: DocumentBody) -> dict[str, int]:
        """Return the heading depths that the document structure does not give."""
        return {}


class DoclingPdfLoader(DoclingLoader):
    """Reads PDF and image files with docling.

    PDF needs the ``docling`` extra, which installs the layout and table models. The
    loader runs OCR on a PDF only where the PDF has no text layer, except for a PDF
    with at least 80% of pages lacking text, which gets full-page OCR. It reads
    heading depth from the bookmarks of the PDF. A PDF with no bookmarks whose
    headings carry dotted numbers gets its depth from the numbers.

    Attributes:
        extensions: The PDF and image formats this loader reads.
        extra: The package extra that installs the models.
        extra_module: The model package that only the extra installs. The core
            docling package is present without the extra, so it cannot prove the
            extra is installed.
    """

    _formats: dict[str, SourceFormat] = {
        ".pdf": SourceFormat.PDF,
        ".png": SourceFormat.IMAGE,
        ".jpg": SourceFormat.IMAGE,
        ".jpeg": SourceFormat.IMAGE,
        ".tif": SourceFormat.IMAGE,
        ".tiff": SourceFormat.IMAGE,
        ".bmp": SourceFormat.IMAGE,
    }
    extensions = frozenset(_formats)
    extra = "docling"
    extra_module = "docling_ibm_models"

    def _converter(self, source: SourceRef, raw: bytes) -> Any:
        """Return the PDF converter, with OCR chosen from the document's text layer."""
        ocr = ocr_choice(raw) if source.extension == ".pdf" else "full"
        return pdf_converter(ocr)

    def _heading_depths(self, body: DocumentBody) -> dict[str, int]:
        """Return heading depths read from the dotted numbers in heading text."""
        return numbered_depths(body)
