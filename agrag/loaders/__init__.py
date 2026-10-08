"""Document loaders: turn files, directories and raw text into Documents.

The docling loaders live in ``agrag.loaders.docling``. PDF and image files need the
``docling`` extra.
"""

from agrag.loaders.corpus import (
    ChatLoader,
    CsvLoader,
    JsonlLoader,
    JsonLoader,
    TextLoader,
    XmlLoader,
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
    "ChatLoader",
    "CsvLoader",
    "DecodeError",
    "DocumentConversionError",
    "DocumentTooLargeError",
    "ErrorPolicy",
    "IngestResult",
    "IngestionError",
    "JsonLoader",
    "JsonlLoader",
    "LoadStats",
    "LoaderRegistry",
    "MalformedRecordError",
    "MissingExtraError",
    "ReadOptions",
    "TextLoader",
    "XmlLoader",
    "UnsupportedFormatError",
    "registry",
]
