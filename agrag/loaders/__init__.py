"""Document loaders: turn files, directories and raw text into Documents.

The docling loaders live in ``agrag.loaders.docling``. PDF and image files need the
``docling`` extra.
"""

from agrag.loaders.chat import ChatLoader
from agrag.loaders.errors import (
    DecodeError,
    DocumentConversionError,
    DocumentTooLargeError,
    IngestionError,
    MalformedRecordError,
    MissingExtraError,
    UnsupportedFormatError,
)
from agrag.loaders.loader_registry import LoaderRegistry, registry
from agrag.loaders.prose import TextLoader, XmlLoader
from agrag.loaders.records import CsvLoader, JsonlLoader, JsonLoader
from agrag.loaders.types import ErrorPolicy, IngestResult, LoadStats, ReadOptions


registry.register(TextLoader())
registry.register(XmlLoader())
registry.register(CsvLoader())
registry.register(JsonlLoader())
registry.register(JsonLoader())

import agrag.loaders.docling  # noqa: F401


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
