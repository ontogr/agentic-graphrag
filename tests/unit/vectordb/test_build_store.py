"""Tests for build_vector_store and the backend lookup table."""

import typing
from typing import get_args, get_origin

from agrag.vectordb import _VECTOR_STORE_FACTORIES, build_vector_store
from agrag.vectordb.milvus import MilvusVectorStore
from agrag.vectordb.qdrant import QdrantVectorStore
from agrag.vectordb.settings import MilvusSettings, QdrantSettings, WeaviateSettings
from agrag.vectordb.weaviate import WeaviateVectorStore


class TestBuildVectorStore:
    """build_vector_store resolves a name or passes an instance through."""

    def test_build_qdrant_from_name(self) -> None:
        """The "qdrant" name builds a QdrantVectorStore."""
        store = build_vector_store("qdrant")
        assert isinstance(store, QdrantVectorStore)
        assert isinstance(store._settings, QdrantSettings)

    def test_build_weaviate_from_name(self) -> None:
        """The "weaviate" name builds a WeaviateVectorStore."""
        store = build_vector_store("weaviate")
        assert isinstance(store, WeaviateVectorStore)
        assert isinstance(store._settings, WeaviateSettings)

    def test_build_milvus_from_name(self) -> None:
        """The "milvus" name builds a MilvusVectorStore."""
        store = build_vector_store("milvus")
        assert isinstance(store, MilvusVectorStore)
        assert isinstance(store._settings, MilvusSettings)

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
