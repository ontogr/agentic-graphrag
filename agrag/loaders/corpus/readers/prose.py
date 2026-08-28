"""Prose readers: plain text, Markdown, and AsciiDoc."""

import re
from collections.abc import Iterator
from typing import BinaryIO

from markdown_it import MarkdownIt

from agrag.common.data_models.document import HeadingRef, SourceFormat
from agrag.loaders.corpus.base import ProseLoader
from agrag.loaders.corpus.decode import decode_text
from agrag.loaders.corpus.readers._common import (
    EXTENSION_FORMAT,
    build_prose_document,
    read_within_limit,
    source_title,
)
from agrag.loaders.corpus.types import DecodedText, ReadOptions, SourceRef


def _line_start_offsets(text: str) -> list[int]:
    """Return the character offset of the first character of each line.

    Computed once per document so a caller with many headings can look up any line's
    offset in constant time instead of rescanning the text's prefix for each one.

    Args:
        text: The document text, with LF line endings.

    Returns:
        The offset of line ``i``'s first character, indexed by 0-based line number.
    """
    offsets = [0]
    for line in text.split("\n")[:-1]:
        offsets.append(offsets[-1] + len(line) + 1)
    return offsets


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
    ) -> Iterator:
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
        source_format = EXTENSION_FORMAT.get(source.extension, SourceFormat.TXT)
        yield build_prose_document(
            source=source,
            text=decoded.text,
            encoding=decoded.encoding,
            source_format=source_format,
            loader_name="text",
            opts=opts,
            title=source_title(source),
        )


class MarkdownLoader(ProseLoader):
    """Reads Markdown files and records their heading outline.

    Attributes:
        extensions: The ``.md`` and ``.markdown`` extensions.
    """

    extensions = frozenset({".md", ".markdown"})

    def load(
        self,
        source: SourceRef,
        stream: BinaryIO,
        opts: ReadOptions,
        *,
        start_at: int = 0,
    ) -> Iterator:
        """Yield one prose Document with a heading outline.

        Args:
            source: The source to read.
            stream: The open binary stream for the source.
            opts: The read options for this call.
            start_at: Ignored by prose loaders.

        Yields:
            One Document holding the decoded text and its headings.
        """
        raw = read_within_limit(stream, source, opts)
        decoded = decode_text(raw, opts)
        heading_outline, title = self._headings(decoded)
        yield build_prose_document(
            source=source,
            text=decoded.text,
            encoding=decoded.encoding,
            source_format=SourceFormat.MARKDOWN,
            loader_name="markdown",
            opts=opts,
            title=title or source_title(source),
            heading_outline=heading_outline,
        )

    @staticmethod
    def _headings(decoded: DecodedText) -> tuple[list[HeadingRef], str | None]:
        """Parse the heading outline and first-title from decoded Markdown.

        Args:
            decoded: The decoded Markdown text and its metadata.

        Returns:
            The heading outline and the first top-level heading as a title, when
            present.
        """
        md = MarkdownIt()
        tokens = md.parse(decoded.text)
        line_offsets = _line_start_offsets(decoded.text)
        outline: list[HeadingRef] = []
        title: str | None = None
        pending_text: str | None = None
        pending_level: int | None = None
        pending_line: int = 0
        for token in tokens:
            if token.type == "heading_open":
                pending_level = int(token.tag[1:])
                pending_text = None
                pending_line = token.map[0] if token.map else 0
            elif token.type == "inline" and pending_level is not None:
                pending_text = token.content
            elif token.type == "heading_close" and pending_level is not None:
                char_start = line_offsets[pending_line]
                text = pending_text or ""
                if pending_level == 1 and title is None:
                    title = text
                outline.append(
                    HeadingRef(text=text, level=pending_level, char_start=char_start)
                )
                pending_level = None
                pending_text = None
        return outline, title


class AsciiDocLoader(ProseLoader):
    """Reads AsciiDoc files with a regex-based heading scan.

    This reader is the fallback when the docling extra is not installed. It tracks
    headings by level lines (``= Title`` through ``===== Title``) but does not parse
    the rest of the AsciiDoc syntax.

    Attributes:
        extensions: The ``.adoc`` and ``.asciidoc`` extensions.
    """

    extensions = frozenset({".adoc", ".asciidoc"})

    def load(
        self,
        source: SourceRef,
        stream: BinaryIO,
        opts: ReadOptions,
        *,
        start_at: int = 0,
    ) -> Iterator:
        """Yield one prose Document with a heading outline.

        Args:
            source: The source to read.
            stream: The open binary stream for the source.
            opts: The read options for this call.
            start_at: Ignored by prose loaders.

        Yields:
            One Document holding the decoded text and its headings.
        """
        raw = read_within_limit(stream, source, opts)
        decoded = decode_text(raw, opts)
        line_offsets = _line_start_offsets(decoded.text)
        heading_outline: list[HeadingRef] = []
        title: str | None = None
        for line_no, line in enumerate(decoded.text.split("\n")):
            match = re.match(r"^(=+)\s+(.*)$", line)
            if not match:
                continue
            level = len(match.group(1))
            text = match.group(2).strip()
            char_start = line_offsets[line_no]
            if level == 1 and title is None:
                title = text
            heading_outline.append(
                HeadingRef(text=text, level=level, char_start=char_start)
            )
        yield build_prose_document(
            source=source,
            text=decoded.text,
            encoding=decoded.encoding,
            source_format=SourceFormat.ASCIIDOC,
            loader_name="asciidoc",
            opts=opts,
            title=title or source_title(source),
            heading_outline=heading_outline,
        )
