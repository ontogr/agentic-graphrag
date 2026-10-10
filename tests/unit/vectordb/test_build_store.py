"""Tests for build_vector_store.

Covers passthrough of an already-constructed VectorStore instance (named
backends are built in the integration tests).
"""

import pytest
from opentelemetry import trace

from agrag.vectordb import build_vector_store
from agrag.vectordb.qdrant import QdrantVectorStore
from agrag.vectordb.settings import QdrantSettings


class TestBuildVectorStore:
    """build_vector_store resolves a name or passes an instance through."""

    def test_passthrough_instance(self) -> None:
        """An existing VectorStore is returned unchanged."""
        store = QdrantVectorStore(settings=QdrantSettings())
        assert build_vector_store(store) is store

    def test_tracer_with_instance_raises(self) -> None:
        """Passing tracer with an already-built store raises ValueError."""
        store = QdrantVectorStore(settings=QdrantSettings())
        with pytest.raises(ValueError, match="tracer has no effect"):
            build_vector_store(store, tracer=trace.get_tracer("test"))
