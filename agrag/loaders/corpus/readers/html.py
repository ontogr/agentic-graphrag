"""The HTML reader: extracts main content with a CSS selector."""

from collections.abc import Iterator
from typing import BinaryIO

from selectolax.parser import HTMLParser

from agrag.common.data_models.document import SourceFormat
from agrag.loaders.corpus.base import ProseLoader
from agrag.loaders.corpus.decode import decode_text
from agrag.loaders.corpus.readers._common import (
    build_prose_document,
    read_within_limit,
    source_title,
)
from agrag.loaders.corpus.types import ReadOptions, SourceRef


_DEFAULT_SELECTOR = "main, article, body"


class HtmlLoader(ProseLoader):
    """Reads HTML files and keeps the main content.

    Attributes:
        extensions: The ``.html`` and ``.htm`` extensions.
    """

    extensions = frozenset({".html", ".htm"})

    def load(
        self,
        source: SourceRef,
        stream: BinaryIO,
        opts: ReadOptions,
        *,
        start_at: int = 0,
    ) -> Iterator:
        """Yield one prose Document from the selected content root.

        Args:
            source: The source to read.
            stream: The open binary stream for the source.
            opts: The read options. ``opts.html_selector`` overrides the content root.
            start_at: Ignored by prose loaders.

        Yields:
            One Document holding the main content text.
        """
        raw = read_within_limit(stream, source, opts)
        decoded = decode_text(raw, opts)
        selector = opts.html_selector or _DEFAULT_SELECTOR
        tree = HTMLParser(decoded.text)
        node = tree.css_first(selector)
        text = node.text(separator="\n").strip() if node is not None else decoded.text
        yield build_prose_document(
            source=source,
            text=text,
            encoding=decoded.encoding,
            source_format=SourceFormat.HTML,
            loader_name="html",
            opts=opts,
            title=source_title(source),
        )
