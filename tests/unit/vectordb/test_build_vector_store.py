"""Factory selection must not replace an instance or silently discard its tracer."""

import pytest
from opentelemetry import trace

from agrag.vectordb import VectorStoreName, build_vector_store
from agrag.vectordb.milvus import MilvusSettings, MilvusVectorStore
from agrag.vectordb.qdrant import QdrantSettings, QdrantVectorStore


class TestBuildVectorStore:
    """Names construct stores; instances preserve their configuration."""

    @pytest.mark.parametrize("backend", ["qdrant", "milvus"])
    def test_builds_named_store_without_connecting(
        self, backend: VectorStoreName, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Named stores load their configured prefix without opening a service."""
        monkeypatch.setenv(f"{backend.upper()}_COLLECTION_PREFIX", "factory_test")
        store = build_vector_store(backend, tracer=trace.get_tracer("test"))
        assert store.name == backend
        assert store.collection_prefix == "factory_test"

    def test_returns_instance_unchanged(self) -> None:
        """An existing store retains its prefix and identity."""
        store = QdrantVectorStore(settings=QdrantSettings(collection_prefix="unit"))
        assert build_vector_store(store) is store
        milvus = MilvusVectorStore(settings=MilvusSettings(collection_prefix="unit"))
        assert build_vector_store(milvus) is milvus

    def test_rejects_tracer_with_instance(self) -> None:
        """A tracer cannot silently override an instance's tracer."""
        store = QdrantVectorStore(settings=QdrantSettings(collection_prefix="unit"))
        with pytest.raises(ValueError, match="tracer has no effect"):
            build_vector_store(store, tracer=trace.get_tracer("test"))
        milvus = MilvusVectorStore(settings=MilvusSettings(collection_prefix="unit"))
        with pytest.raises(ValueError, match="tracer has no effect"):
            build_vector_store(milvus, tracer=trace.get_tracer("test"))

    def test_rejects_unknown_name(self) -> None:
        """Unknown backend names report a configuration error."""
        with pytest.raises(ValueError, match="Unknown vector store"):
            build_vector_store("unknown")
