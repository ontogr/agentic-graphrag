"""The extension-to-loader registry."""

from agrag.loaders.base import Loader
from agrag.loaders.errors import MissingExtraError, UnsupportedFormatError
from agrag.loaders.types import SourceRef


class LoaderRegistry:
    """Maps each source extension to the one loader that reads it.

    Attributes:
        _by_extension: The loader for each registered extension.
    """

    def __init__(self) -> None:
        """Create an empty registry."""
        self._by_extension: dict[str, Loader] = {}

    def register(self, loader: Loader) -> None:
        """Add a loader for each extension it claims.

        Registering a loader of a type that already holds an extension is a no-op,
        so calling ``register_default_loaders`` twice is safe.

        Args:
            loader: The loader to register.

        Raises:
            ValueError: Another loader type already holds one of the extensions.
        """
        for extension in loader.extensions:
            existing = self._by_extension.get(extension)
            if existing is not None and type(existing) is not type(loader):
                raise ValueError(
                    f"extension {extension!r} is claimed by both "
                    f"{type(existing).__name__} and {type(loader).__name__}"
                )
        for extension in loader.extensions:
            self._by_extension.setdefault(extension, loader)

    def for_source(self, source: SourceRef) -> Loader:
        """Return the loader for a source's extension.

        Args:
            source: The source to find a loader for.

        Returns:
            The loader registered for the source's extension.

        Raises:
            UnsupportedFormatError: No loader claims the source's extension.
            MissingExtraError: The loader needs a package extra that is not
                installed.
        """
        loader = self._by_extension.get(source.extension)
        if loader is None:
            raise UnsupportedFormatError(source.extension)
        if loader.extra is not None and not loader.is_available():
            raise MissingExtraError(source.extension, loader.extra)
        return loader
