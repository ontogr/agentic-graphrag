"""The docling loader package.

Importing this package registers ``DoclingLoader`` with the corpus registry. The core
loaders win by default for Markdown, HTML, and CSV; docling wins for PDF, DOCX, PPTX,
images, AsciiDoc, and XML.
"""

from agrag.loaders.corpus import registry
from agrag.loaders.docling.loader import DoclingLoader


_loader = DoclingLoader()

_PREFER_TRUE = frozenset(
    {
        ".pdf",
        ".docx",
        ".pptx",
        ".png",
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
        ".bmp",
        ".adoc",
        ".asciidoc",
        ".xml",
    }
)

registry.register(_loader, prefer=True, extensions=_PREFER_TRUE)
registry.register(_loader, prefer=False, extensions=_loader.extensions - _PREFER_TRUE)

__all__ = ["DoclingLoader"]
