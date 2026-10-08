"""The docling loaders.

Importing this package registers ``DoclingLoader`` and ``DoclingPdfLoader`` with the
corpus registry. Docling reads every format it claims. The core loaders keep plain
text, XML and the record formats.
"""

from agrag.loaders.corpus import registry
from agrag.loaders.docling.loader import DoclingLoader, DoclingPdfLoader


registry.register(DoclingLoader(), prefer=True)
registry.register(DoclingPdfLoader(), prefer=True)

__all__ = ["DoclingLoader", "DoclingPdfLoader"]
