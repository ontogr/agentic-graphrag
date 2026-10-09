"""Docling-backed loaders.

``DoclingLoader`` reads the formats that need no model: Markdown, HTML, AsciiDoc, DOCX,
PPTX and XLSX. ``DoclingPdfLoader`` reads PDF and image files and needs the ``docling``
extra. Importing this module does not import the docling library: the loaders import
it when they convert.
"""

import hashlib
import io
from collections.abc import Iterator
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, BinaryIO

from docling_core.types.doc import DoclingDocument

from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.loaders.corpus.base import ProseLoader
from agrag.loaders.corpus.errors import DocumentConversionError
from agrag.loaders.corpus.readers._common import read_within_limit, source_title
from agrag.loaders.corpus.types import ReadOptions, SourceRef
from agrag.loaders.docling._converters import ocr_choice, pdf_converter, slim_converter
from agrag.loaders.docling._pdf_levels import numbered_depths
from agrag.loaders.docling._sections import (
    DocumentBody,
    read_body,
    sections_from_docling,
)


if TYPE_CHECKING:
    from docling.document_converter import DocumentConverter


_SLIM_FORMATS: dict[str, SourceFormat] = {
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
_PDF_FORMATS: dict[str, SourceFormat] = {
    ".pdf": SourceFormat.PDF,
    ".png": SourceFormat.IMAGE,
    ".jpg": SourceFormat.IMAGE,
    ".jpeg": SourceFormat.IMAGE,
    ".tif": SourceFormat.IMAGE,
    ".tiff": SourceFormat.IMAGE,
    ".bmp": SourceFormat.IMAGE,
}
# Docling picks the parser from the file name, and it does not know these suffixes.
_DOCLING_SUFFIX = {".markdown": ".md"}


class DoclingLoader(ProseLoader):
    """Reads Markdown, HTML, AsciiDoc, DOCX, PPTX and XLSX files with docling.

    The loader gives a document its sections from the structure that docling finds. It
    needs no model and no extra. The content hash comes from the raw source bytes,
    because the parsed output can change between docling versions and runs.

    Attributes:
        extensions: The formats this loader reads.
    """

    extensions = frozenset(_SLIM_FORMATS)
    _formats = _SLIM_FORMATS

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
            One Document. Its text is the docling Markdown export, and its sections
            hold the content. Its title is the first heading, or the file name when
            the source has no heading.

        Raises:
            DocumentTooLargeError: The source is larger than the configured byte
                limit.
            DocumentConversionError: Docling could not parse or convert the source.
            ValueError: ``opts.max_document_bytes`` is not a positive integer.
        """
        raw = read_within_limit(stream, source, opts)
        try:
            document = self._convert(source, raw)
        except Exception as exc:
            raise DocumentConversionError(
                f"docling could not convert {source.uri}: {exc}"
            ) from exc
        text = document.export_to_markdown()
        try:
            loader_version = version("docling")
        except PackageNotFoundError:
            loader_version = None
        body = read_body(document)
        sections = sections_from_docling(body, self._depths(body))
        title = next((s.heading for s in sections if s.heading), None)
        yield Document(
            text=text if opts.store_text else "",
            title=title or source_title(source),
            uri=source.uri,
            source_format=self._formats[source.extension],
            family=DocumentFamily.PROSE,
            content_hash=hashlib.sha256(raw).hexdigest(),
            loader_name="docling",
            loader_version=loader_version,
            char_count=len(text),
            line_count=text.count("\n") + 1,
            sections=sections if opts.store_text else [],
        )

    def _convert(self, source: SourceRef, raw: bytes) -> DoclingDocument:
        """Convert the bytes and return the parsed document."""
        from docling.datamodel.base_models import DocumentStream  # noqa: PLC0415

        name = source.uri
        if source.extension in _DOCLING_SUFFIX:
            name = name[: -len(source.extension)] + _DOCLING_SUFFIX[source.extension]
        stream = DocumentStream(name=name, stream=io.BytesIO(raw))
        return self._converter(raw, source).convert(stream).document

    def _converter(self, raw: bytes, source: SourceRef) -> "DocumentConverter":
        return slim_converter()

    def _depths(self, body: DocumentBody) -> dict[str, int]:
        return {}


class DoclingPdfLoader(DoclingLoader):
    """Reads PDF and image files with docling.

    PDF needs the ``docling`` extra, which installs the layout and table models. The
    loader runs OCR on a PDF only where the PDF has no text layer. It reads heading
    depth from the bookmarks of the PDF. A PDF with no bookmarks whose headings carry
    dotted numbers gets its depth from the numbers.

    Attributes:
        extensions: The PDF and image formats this loader reads.
        extra: The package extra that installs the models.
        extra_module: A module that only the extra installs.
    """

    extensions = frozenset(_PDF_FORMATS)
    extra = "docling"
    extra_module = "docling_ibm_models"
    _formats = _PDF_FORMATS

    def _converter(self, raw: bytes, source: SourceRef) -> "DocumentConverter":
        is_pdf = source.extension == ".pdf"
        return pdf_converter(ocr_choice(raw) if is_pdf else "full")

    def _depths(self, body: DocumentBody) -> dict[str, int]:
        return numbered_depths(body)
