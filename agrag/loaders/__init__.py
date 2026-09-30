"""Document loaders: turn files, directories and raw text into Documents.

The docling loader needs the ``docling`` extra and lives in ``agrag.loaders.docling``.
"""

from agrag.loaders.corpus import (
    AsciiDocLoader,
    ChatLoader,
    CsvLoader,
    HtmlLoader,
    JsonlLoader,
    JsonLoader,
    MarkdownLoader,
    TextLoader,
    registry,
)
from agrag.loaders.corpus.errors import (
    DecodeError,
    DocumentConversionError,
    DocumentTooLargeError,
    IngestionError,
    MalformedRecordError,
    MissingExtraError,
    UnsupportedFormatError,
)
from agrag.loaders.corpus.registry import LoaderRegistry
from agrag.loaders.corpus.types import ErrorPolicy, IngestResult, LoadStats, ReadOptions


__all__ = [
    "AsciiDocLoader",
    "ChatLoader",
    "CsvLoader",
    "DecodeError",
    "DocumentConversionError",
    "DocumentTooLargeError",
    "ErrorPolicy",
    "HtmlLoader",
    "IngestResult",
    "IngestionError",
    "JsonLoader",
    "JsonlLoader",
    "LoadStats",
    "LoaderRegistry",
    "MalformedRecordError",
    "MarkdownLoader",
    "MissingExtraError",
    "ReadOptions",
    "TextLoader",
    "UnsupportedFormatError",
    "registry",
]
