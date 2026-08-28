"""Docling-backed loader for PDF, DOCX, PPTX, and image sources.

Importing this module does not import the docling library. The loader imports docling
inside ``load`` so that the rest of the package works without the ``docling`` extra
installed. The registry raises ``MissingExtraError`` when a source needs this loader but
the extra is missing.
"""

import hashlib
import io
from collections.abc import Iterator
from importlib.metadata import version
from typing import BinaryIO

from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.loaders.corpus.base import ProseLoader
from agrag.loaders.corpus.errors import DocumentConversionError, DocumentTooLargeError
from agrag.loaders.corpus.types import ReadOptions, SourceRef


_DOCLING_FORMATS: dict[str, SourceFormat] = {
    ".pdf": SourceFormat.PDF,
    ".docx": SourceFormat.DOCX,
    ".pptx": SourceFormat.PPTX,
    ".png": SourceFormat.IMAGE,
    ".jpg": SourceFormat.IMAGE,
    ".jpeg": SourceFormat.IMAGE,
    ".tif": SourceFormat.IMAGE,
    ".tiff": SourceFormat.IMAGE,
    ".bmp": SourceFormat.IMAGE,
    ".md": SourceFormat.MARKDOWN,
    ".html": SourceFormat.HTML,
    ".csv": SourceFormat.CSV,
    ".adoc": SourceFormat.ASCIIDOC,
    ".asciidoc": SourceFormat.ASCIIDOC,
    ".xml": SourceFormat.XML,
}


class DoclingLoader(ProseLoader):
    """Reads documents with the docling library.

    This loader registers for the PDF, DOCX, PPTX, and image formats, plus the Markdown,
    HTML, CSV, AsciiDoc, and XML formats it can also parse. It wins by default only for
    the
    formats no core loader claims.

    Attributes:
        extensions: Every format docling can read.
        extra: The package extra required to use this loader.
    """

    extensions = frozenset(_DOCLING_FORMATS.keys())
    extra = "docling"

    def load(
        self,
        source: SourceRef,
        stream: BinaryIO,
        opts: ReadOptions,
        *,
        start_at: int = 0,
    ) -> Iterator[Document]:
        """Yield one prose Document parsed by docling.

        The content hash comes from the raw source bytes, not from docling's parsed
        output,
        because the parsed output can change between docling versions and runs.

        Args:
            source: The source to read.
            stream: The open binary stream for the source.
            opts: The read options.
            start_at: Ignored by prose loaders.

        Yields:
            One Document holding docling's Markdown export of the source.

        Raises:
            MissingExtraError: The docling extra is not installed.
            DocumentTooLargeError: The source is larger than the configured byte
                limit.
            DocumentConversionError: Docling could not parse or convert the source.
            ValueError: ``opts.max_document_bytes`` is not a positive integer.
        """
        from docling.datamodel.document import (  # noqa: PLC0415
            DocumentStream,
        )
        from docling.document_converter import (  # noqa: PLC0415
            DocumentConverter,
        )

        limit = opts.max_document_bytes
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise ValueError("max_document_bytes must be a positive integer")

        if source.byte_size is not None and source.byte_size > limit:
            raise DocumentTooLargeError(
                f"{source.uri} is {source.byte_size} bytes, over the {limit} limit"
            )

        # A stream with no reported (or a stale) byte_size still must not be read
        # past the limit, so cap the read itself rather than trusting the size
        # check above alone.
        raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise DocumentTooLargeError(f"{source.uri} is over the {limit} byte limit")
        content_hash = hashlib.sha256(raw).hexdigest()
        converter = DocumentConverter()
        try:
            result = converter.convert(
                DocumentStream(name=source.uri, stream=io.BytesIO(raw))
            )
        except Exception as exc:
            raise DocumentConversionError(
                f"docling could not convert {source.uri}: {exc}"
            ) from exc
        text = result.document.export_to_markdown()

        loader_version = None
        try:
            loader_version = version("docling")
        except Exception:  # noqa: BLE001 - version is best-effort metadata
            loader_version = None

        yield Document(
            text=text if opts.store_text else "",
            title=source.uri,
            uri=source.uri,
            source_format=_DOCLING_FORMATS[source.extension],
            family=DocumentFamily.PROSE,
            content_hash=content_hash,
            loader_name="docling",
            loader_version=loader_version,
            encoding=None,
            char_count=len(text),
            line_count=text.count("\n") + 1,
            metadata={"_docling_document": result.document},
        )
