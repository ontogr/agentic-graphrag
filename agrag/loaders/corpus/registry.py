"""The extension-to-loader registry."""

import importlib.util
from dataclasses import dataclass

from agrag.loaders.corpus.base import Loader
from agrag.loaders.corpus.errors import MissingExtraError, UnsupportedFormatError
from agrag.loaders.corpus.types import SourceRef


@dataclass(slots=True)
class _Entry:
    """One registration of a loader for an extension."""

    loader: Loader
    prefer: bool


class LoaderRegistry:
    """Maps a source extension to the loader that reads it.

    The registry picks a loader by file extension first. When more than one loader
    claims
    the same extension, the loader registered with ``prefer=True`` wins; when several
    loaders
    are preferred, the last preferred registration wins.

    Attributes:
        _by_extension: The registered loaders for each extension, in registration order.
    """

    def __init__(self) -> None:
        """Create an empty registry."""
        self._by_extension: dict[str, list[_Entry]] = {}

    def register(
        self,
        loader: Loader,
        *,
        prefer: bool = False,
        extensions: "set[str] | frozenset[str] | None" = None,
    ) -> None:
        """Add a loader to the registry.

        Registering the same loader for the same extension more than once is a no-op, so
        importing a package that registers loaders repeatedly stays safe.

        Args:
            loader: The loader to register.
            prefer: Set this to True to make the loader the default for its extensions.
                Leave it False to register the loader only as an explicit, named option.
            extensions: Only register ``loader`` for these extensions. Defaults to every
                extension the loader advertises. A caller that wants different
                precedence per
                extension registers the same loader twice with different ``extensions``
                sets.
        """
        entry = _Entry(loader=loader, prefer=prefer)
        for ext in extensions if extensions is not None else loader.extensions:
            existing = self._by_extension.setdefault(ext, [])
            if entry not in existing:
                existing.append(entry)

    def for_source(self, source: SourceRef) -> Loader:
        """Return the default loader for a source.

        Args:
            source: The source to find a loader for.

        Returns:
            The registered loader with the highest precedence for the source's
            extension.

        Raises:
            UnsupportedFormatError: No loader claims the source's extension.
            MissingExtraError: A loader is mapped to the extension, but its package
            extra
                failed to import.
        """
        entries = self._by_extension.get(source.extension)
        if not entries:
            raise UnsupportedFormatError(source.extension)

        preferred = [entry for entry in entries if entry.prefer]
        chosen = preferred[-1].loader if preferred else entries[0].loader

        if chosen.extra is not None and importlib.util.find_spec(chosen.extra) is None:
            raise MissingExtraError(source.extension, chosen.extra)

        return chosen
