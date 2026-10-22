"""Factory selection must not replace an instance or silently discard its tracer."""

import pytest
from opentelemetry import trace

from agrag.vectordb import build_vector_store
from agrag.vectordb.qdrant import QdrantSettings, QdrantVectorStore


class TestBuildVectorStore:
    """Names construct stores; instances preserve their configuration."""

    def test_returns_instance_unchanged(self) -> None:
        """An existing store retains its prefix and identity."""
        store = QdrantVectorStore(settings=QdrantSettings(collection_prefix="unit"))
        assert build_vector_store(store) is store

    def test_rejects_tracer_with_instance(self) -> None:
        """A tracer cannot silently override an instance's tracer."""
        store = QdrantVectorStore(settings=QdrantSettings(collection_prefix="unit"))
        with pytest.raises(ValueError, match="tracer has no effect"):
            build_vector_store(store, tracer=trace.get_tracer("test"))

    def test_rejects_unknown_name(self) -> None:
        """Unknown backend names report a configuration error."""
        with pytest.raises(ValueError, match="Unknown vector store"):
            build_vector_store("unknown")
