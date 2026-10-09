"""The docling loaders.

Docling reads every format it claims. The core loaders keep plain text, XML and the
record formats.
"""

from agrag.loaders.docling.loader import DoclingLoader, DoclingPdfLoader


__all__ = ["DoclingLoader", "DoclingPdfLoader"]
