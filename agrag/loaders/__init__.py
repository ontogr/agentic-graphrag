"""Document loaders: turn files, directories and raw text into Documents.

The docling loaders live in ``agrag.loaders.docling``. PDF and image files need the
``docling`` extra.
"""

from agrag.loaders.chat import ChatLoader
from agrag.loaders.defaults import register_default_loaders
from agrag.loaders.errors import (
    DecodeError,
    DocumentConversionError,
    DocumentTooLargeError,
    IngestionError,
    MalformedRecordError,
    MissingExtraError,
    UnsupportedFormatError,
)
from agrag.loaders.loader_registry import LoaderRegistry
from agrag.loaders.prose import TextLoader, XmlLoader
from agrag.loaders.records import CsvLoader, JsonlLoader, JsonLoader
from agrag.loaders.types import ErrorPolicy, IngestResult, LoadStats, ReadOptions


registry = LoaderRegistry()
register_default_loaders(registry)
"""The default registry, with every built-in loader registered.

Import it with ``from agrag.loaders import registry``. A new ``LoaderRegistry()``
starts empty and rejects every format until loaders are registered on it.
"""


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
    "register_default_loaders",
    "registry",
]
