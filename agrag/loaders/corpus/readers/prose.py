"""Prose readers: plain text and XML."""

from collections.abc import Iterator
from typing import BinaryIO

from selectolax.parser import HTMLParser

from agrag.common.data_models.document import Document, SourceFormat
from agrag.loaders.corpus.base import ProseLoader
from agrag.loaders.corpus.decode import decode_text
from agrag.loaders.corpus.readers.common import (
    EXTENSION_FORMAT,
    build_prose_document,
    read_within_limit,
    source_title,
    text_sections,
)
from agrag.loaders.corpus.types import ReadOptions, SourceRef


class TextLoader(ProseLoader):
    """Reads plain-text and log files as one document each.

    Attributes:
        extensions: The ``.txt`` and ``.log`` extensions.
    """

    extensions = frozenset({".txt", ".log"})

    def load(
        self,
        source: SourceRef,
        stream: BinaryIO,
        opts: ReadOptions,
        *,
        start_at: int = 0,
    ) -> Iterator[Document]:
        """Yield one prose Document from the source.

        Args:
            source: The source to read.
            stream: The open binary stream for the source.
            opts: The read options for this call.
            start_at: Ignored by prose loaders.

        Yields:
            One Document holding the decoded text.
        """
        raw = read_within_limit(stream, source, opts)
        decoded = decode_text(raw, opts)
        source_format = EXTENSION_FORMAT[source.extension]
        yield build_prose_document(
            source=source,
            text=decoded.text,
            encoding=decoded.encoding,
            source_format=source_format,
            loader_name="text",
            opts=opts,
            title=source_title(source),
            sections=text_sections(decoded.text),
        )


class XmlLoader(ProseLoader):
    """Reads an XML file as the text of its elements.

    The loader drops the tags and keeps the text of each element on its own line.
    Text inside a CDATA section is not kept.

    Attributes:
        extensions: The ``.xml`` extension.
    """

    extensions = frozenset({".xml"})

    def load(
        self,
        source: SourceRef,
        stream: BinaryIO,
        opts: ReadOptions,
        *,
        start_at: int = 0,
    ) -> Iterator[Document]:
        """Yield one prose Document from the text of the elements.

        Args:
            source: The source to read.
            stream: The open binary stream for the source.
            opts: The read options for this call.
            start_at: Ignored by prose loaders.

        Yields:
            One Document holding the element text.
        """
        raw = read_within_limit(stream, source, opts)
        decoded = decode_text(raw, opts)
        text = HTMLParser(decoded.text).text(separator="\n", strip=True)
        yield build_prose_document(
            source=source,
            text=text,
            encoding=decoded.encoding,
            source_format=SourceFormat.XML,
            loader_name="xml",
            opts=opts,
            title=source_title(source),
            sections=text_sections(text),
        )
