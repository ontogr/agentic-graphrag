"""The corpus loaders package.

Importing this package registers every core loader with the module-level ``registry``
singleton. The docling extra registers itself on top of this when installed.
"""

from agrag.loaders.corpus.readers.chat import ChatLoader
from agrag.loaders.corpus.readers.prose import TextLoader, XmlLoader
from agrag.loaders.corpus.readers.records import CsvLoader, JsonlLoader, JsonLoader
from agrag.loaders.corpus.registry import LoaderRegistry


registry: LoaderRegistry = LoaderRegistry()
registry.register(TextLoader())
registry.register(XmlLoader())
registry.register(CsvLoader())
registry.register(JsonlLoader())
registry.register(JsonLoader())

__all__ = [
    "registry",
    "ChatLoader",
    "TextLoader",
    "XmlLoader",
    "CsvLoader",
    "JsonLoader",
    "JsonlLoader",
]
