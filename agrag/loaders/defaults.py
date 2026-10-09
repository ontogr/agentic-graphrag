"""The loaders that the corpus registry holds by default."""

from agrag.loaders.docling import DoclingLoader, DoclingPdfLoader
from agrag.loaders.loader_registry import LoaderRegistry
from agrag.loaders.prose import TextLoader, XmlLoader
from agrag.loaders.records import CsvLoader, JsonlLoader, JsonLoader


def register_default_loaders(target: LoaderRegistry) -> None:
    """Register every default loader on a registry.

    Docling reads the rich formats and the PDF and image formats. The core readers
    keep plain text, XML and the record formats. No extension has two loaders, so
    the order of these calls does not change which loader reads a source.

    Args:
        target: The registry to fill. Calling this twice on the same registry
            registers the same loaders again and changes nothing.
    """
    target.register(TextLoader())
    target.register(XmlLoader())
    target.register(CsvLoader())
    target.register(JsonlLoader())
    target.register(JsonLoader())
    target.register(DoclingLoader())
    target.register(DoclingPdfLoader())


def default_registry() -> LoaderRegistry:
    """Return a new registry with every default loader registered.

    ``agrag.loaders.registry`` is the shared instance built by this function.
    A bare ``LoaderRegistry()`` starts empty and rejects every format.
    """
    registry = LoaderRegistry()
    register_default_loaders(registry)
    return registry
