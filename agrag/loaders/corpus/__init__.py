"""The corpus loaders package.

Importing this package registers every core loader with the module-level ``registry``
singleton. The docling extra registers itself on top of this when installed.
"""

from agrag.loaders.corpus.readers.html import HtmlLoader
from agrag.loaders.corpus.readers.prose import (
    AsciiDocLoader,
    MarkdownLoader,
    TextLoader,
)
from agrag.loaders.corpus.readers.records import CsvLoader, JsonlLoader, JsonLoader
from agrag.loaders.corpus.registry import LoaderRegistry


registry: LoaderRegistry = LoaderRegistry()
registry.register(TextLoader(), prefer=True)
registry.register(MarkdownLoader(), prefer=True)
# Docling is the default for .adoc/.asciidoc when installed (ADR 0006): its structural
# parser beats this reader's regex headings-only scan. Registering prefer=False here,
# mirroring how docling itself defers on .md/.html/.csv, makes that precedence hold
# regardless of import order instead of depending on which package registers last.
registry.register(AsciiDocLoader(), prefer=False)
registry.register(HtmlLoader(), prefer=True)
registry.register(CsvLoader(), prefer=True)
registry.register(JsonlLoader(), prefer=True)
registry.register(JsonLoader(), prefer=True)

__all__ = [
    "registry",
    "HtmlLoader",
    "TextLoader",
    "MarkdownLoader",
    "AsciiDocLoader",
    "CsvLoader",
    "JsonLoader",
    "JsonlLoader",
]
