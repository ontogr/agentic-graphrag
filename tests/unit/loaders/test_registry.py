"""Tests for LoaderRegistry in agrag.loaders.loader_registry.

A registry maps each extension to one loader. Registering the same loader type
again is a no-op. Registering a different loader type for a held extension raises.
"""

import pytest

from agrag.common.data_models.document import DocumentFamily
from agrag.loaders.base import Loader
from agrag.loaders.errors import MissingExtraError, UnsupportedFormatError
from agrag.loaders.loader_registry import LoaderRegistry
from agrag.loaders.types import SourceRef


class _StubLoader(Loader):
    extensions = frozenset({".stub"})
    family = DocumentFamily.PROSE

    def load(self, source, stream, opts, *, start_at=0):  # type: ignore[no-untyped-def]
        yield from ()


class _OtherStubLoader(Loader):
    extensions = frozenset({".stub"})
    family = DocumentFamily.PROSE

    def load(self, source, stream, opts, *, start_at=0):  # type: ignore[no-untyped-def]
        yield from ()


class _ExtraLoader(Loader):
    extensions = frozenset({".extra"})
    family = DocumentFamily.PROSE
    extra = "this_extra_does_not_exist"

    def load(self, source, stream, opts, *, start_at=0):  # type: ignore[no-untyped-def]
        yield from ()


class _DottedExtraLoader(Loader):
    extensions = frozenset({".dotted"})
    family = DocumentFamily.PROSE
    extra = "dotted_extra"
    extra_module = "this_extra_parent_does_not_exist.module"

    def load(self, source, stream, opts, *, start_at=0):  # type: ignore[no-untyped-def]
        yield from ()


class TestLoaderRegistry:
    """Verify lookup, double registration, conflicts and extra detection."""

    def test_returns_the_loader_registered_for_the_extension(self) -> None:
        """A registered extension maps to its loader."""
        registry = LoaderRegistry()
        loader = _StubLoader()
        registry.register(loader)

        assert registry.for_source(SourceRef(uri="x.stub", extension=".stub")) is loader

    def test_registering_the_same_loader_type_twice_keeps_the_first(self) -> None:
        """A second loader of the same type does not replace or duplicate the first."""
        registry = LoaderRegistry()
        first = _StubLoader()
        registry.register(first)
        registry.register(_StubLoader())

        assert registry.for_source(SourceRef(uri="x.stub", extension=".stub")) is first

    def test_registering_a_different_loader_type_for_a_claimed_extension_raises(
        self,
    ) -> None:
        """Two loader types cannot share an extension."""
        registry = LoaderRegistry()
        registry.register(_StubLoader())

        with pytest.raises(ValueError, match=r"\.stub"):
            registry.register(_OtherStubLoader())

    def test_a_rejected_registration_adds_none_of_its_extensions(self) -> None:
        """A conflict leaves the registry as it was before the call."""
        registry = LoaderRegistry()
        registry.register(_StubLoader())

        class _Overlapping(Loader):
            extensions = frozenset({".fresh", ".stub"})
            family = DocumentFamily.PROSE

            def load(self, source, stream, opts, *, start_at=0):  # type: ignore[no-untyped-def]
                yield from ()

        with pytest.raises(ValueError):
            registry.register(_Overlapping())

        with pytest.raises(UnsupportedFormatError):
            registry.for_source(SourceRef(uri="x.fresh", extension=".fresh"))

    def test_missing_extra_raises(self) -> None:
        """A loader whose extra is not importable raises MissingExtraError."""
        registry = LoaderRegistry()
        registry.register(_ExtraLoader())

        with pytest.raises(MissingExtraError) as error:
            registry.for_source(SourceRef(uri="x.extra", extension=".extra"))

        assert error.value.extension == ".extra"
        assert error.value.extra == "this_extra_does_not_exist"

    def test_dotted_extra_module_with_missing_parent_raises_missing_extra(self) -> None:
        """A dotted extra module whose parent package is absent counts as missing."""
        registry = LoaderRegistry()
        registry.register(_DottedExtraLoader())

        with pytest.raises(MissingExtraError) as error:
            registry.for_source(SourceRef(uri="x.dotted", extension=".dotted"))

        assert error.value.extra == "dotted_extra"
