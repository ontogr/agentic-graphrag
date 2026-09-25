"""Tests for build_vector_store and the backend lookup table.

Covers passthrough of an already-constructed VectorStore instance (named
backends are built in the integration tests), and a reflection check that
every ``Literal`` backend name in ``build_vector_store``'s type annotation has
a matching entry in ``_VECTOR_STORE_FACTORIES``.
"""

import typing
from typing import get_args, get_origin

from agrag.vectordb import _VECTOR_STORE_FACTORIES, build_vector_store
from agrag.vectordb.qdrant import QdrantVectorStore
from agrag.vectordb.settings import QdrantSettings


class TestBuildVectorStore:
    """build_vector_store resolves a name or passes an instance through."""

    def test_passthrough_instance(self) -> None:
        """An existing VectorStore is returned unchanged."""
        store = QdrantVectorStore(settings=QdrantSettings())
        assert build_vector_store(store) is store


class TestBackendTable:
    """Every Literal backend name must have a factory entry."""

    def test_every_literal_value_has_a_table_entry(self) -> None:
        """The Literal and the factory table stay in sync."""
        annotation = build_vector_store.__annotations__["value"]
        union_args = get_args(annotation)
        literal = next(a for a in union_args if get_origin(a) is typing.Literal)
        for name in get_args(literal):
            assert name in _VECTOR_STORE_FACTORIES
