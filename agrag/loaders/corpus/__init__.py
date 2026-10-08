"""The corpus loaders package.

Importing this package registers every core loader with the module-level ``registry``
singleton. The docling extra registers itself on top of this when installed.
"""

from agrag.loaders.corpus.readers.chat import ChatLoader
from agrag.loaders.corpus.readers.prose import TextLoader, XmlLoader
from agrag.loaders.corpus.readers.records import CsvLoader, JsonlLoader, JsonLoader
from agrag.loaders.corpus.registry import LoaderRegistry


registry: LoaderRegistry = LoaderRegistry()
registry.register(TextLoader(), prefer=True)
registry.register(XmlLoader(), prefer=True)
registry.register(CsvLoader(), prefer=True)
registry.register(JsonlLoader(), prefer=True)
registry.register(JsonLoader(), prefer=True)

__all__ = [
    "registry",
    "ChatLoader",
    "TextLoader",
    "XmlLoader",
    "CsvLoader",
    "JsonLoader",
    "JsonlLoader",
]
