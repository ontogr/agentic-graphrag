"""Tests for the extension-to-loader registry."""

from agrag.common.data_models.document import DocumentFamily
from agrag.loaders.corpus.base import Loader
from agrag.loaders.corpus.errors import (
    MissingExtraError,
    UnsupportedFormatError,
)
from agrag.loaders.corpus.registry import LoaderRegistry
from agrag.loaders.corpus.types import SourceRef


class _StubLoader(Loader):
    extensions = frozenset({".stub"})
    family = DocumentFamily.PROSE

    def load(self, source, stream, opts, *, start_at=0):  # type: ignore[no-untyped-def]
        yield from ()


class TestLoaderRegistry:
    """Verify precedence, lookup, and extra detection."""

    def test_prefer_wins_over_fallback(self) -> None:
        """A loader registered with prefer=True beats a non-preferred one."""
        registry = LoaderRegistry()
        fallback = _StubLoader()
        preferred = _StubLoader()
        registry.register(fallback)
        registry.register(preferred, prefer=True)
        assert (
            registry.for_source(SourceRef(uri="x.stub", extension=".stub")) is preferred
        )

    def test_last_preferred_registration_wins(self) -> None:
        """Among several preferred loaders the last one registered wins."""
        registry = LoaderRegistry()
        first = _StubLoader()
        second = _StubLoader()
        registry.register(first, prefer=True)
        registry.register(second, prefer=True)
        assert registry.for_source(SourceRef(uri="x.stub", extension=".stub")) is second

    def test_unsupported_extension_raises(self) -> None:
        """An unknown extension raises UnsupportedFormatError."""
        registry = LoaderRegistry()
        try:
            registry.for_source(SourceRef(uri="x.unknown", extension=".unknown"))
        except UnsupportedFormatError:
            return
        raise AssertionError("expected UnsupportedFormatError")

    def test_registration_is_idempotent(self) -> None:
        """Registering the same loader twice for one extension is a no-op."""
        registry = LoaderRegistry()
        loader = _StubLoader()
        registry.register(loader, prefer=True)
        registry.register(loader, prefer=True)
        assert registry.for_source(SourceRef(uri="x.stub", extension=".stub")) is loader

    def test_missing_extra_raises(self) -> None:
        """A loader whose extra is not importable raises MissingExtraError."""
        registry = LoaderRegistry()

        class _ExtraLoader(Loader):
            extensions = frozenset({".extra"})
            extra = "this_extra_does_not_exist"

            def load(self, source, stream, opts, *, start_at=0):  # type: ignore[no-untyped-def]
                yield from ()

        registry.register(_ExtraLoader(), prefer=True)
        try:
            registry.for_source(SourceRef(uri="x.extra", extension=".extra"))
        except MissingExtraError as exc:
            assert exc.extension == ".extra"
            assert exc.extra == "this_extra_does_not_exist"
            return
        raise AssertionError("expected MissingExtraError")

    def test_falls_back_to_non_preferred_loader_when_preferred_extra_missing(
        self,
    ) -> None:
        """A missing extra on the preferred loader falls back to a plain loader."""
        registry = LoaderRegistry()

        class _ExtraLoader(Loader):
            extensions = frozenset({".mixed"})
            extra = "this_extra_does_not_exist"
            family = DocumentFamily.PROSE

            def load(self, source, stream, opts, *, start_at=0):  # type: ignore[no-untyped-def]
                yield from ()

        fallback = _StubLoader()
        registry.register(fallback, extensions={".mixed"})
        registry.register(_ExtraLoader(), prefer=True, extensions={".mixed"})
        assert (
            registry.for_source(SourceRef(uri="x.mixed", extension=".mixed"))
            is fallback
        )

    def test_extensions_allow_list_limits_scope(self) -> None:
        """A loader registered for a subset of its extensions claims only those."""
        registry = LoaderRegistry()
        registry.register(_StubLoader(), prefer=True, extensions={".stub"})
        assert (
            registry.for_source(SourceRef(uri="x.stub", extension=".stub")) is not None
        )
