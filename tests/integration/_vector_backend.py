"""Select the vector-store implementation used by integration tests."""

import os

from agrag.vectordb.base import VectorStore
from agrag.vectordb.milvus import MilvusSettings, MilvusVectorStore
from agrag.vectordb.qdrant import QdrantSettings, QdrantVectorStore
from agrag.vectordb.weaviate import WeaviateSettings, WeaviateVectorStore
from tests.integration._fake_vector_store import FakeVectorStore


def selected_vector_stores() -> tuple[str, ...]:
    """Return requested vector store names, defaulting to the in-memory fake."""
    raw_names = os.environ.get("AGRAG_TEST_VECTOR_STORES", "fake")
    names = tuple(name.strip().lower() for name in raw_names.split(",") if name.strip())
    if not names:
        return ("fake",)
    if len(names) != len(set(names)):
        raise ValueError("AGRAG_TEST_VECTOR_STORES contains duplicate names")
    unknown = set(names) - {"fake", "qdrant", "milvus", "weaviate"}
    if unknown:
        raise ValueError(f"Unsupported vector store selection: {sorted(unknown)}")
    return names


def build_vector_store(name: str, *, collection_prefix: str = "test") -> VectorStore:
    """Build the selected vector store without importing optional clients."""
    if name == "fake":
        return FakeVectorStore(collection_prefix=collection_prefix)
    if name == "qdrant":
        return QdrantVectorStore(
            settings=QdrantSettings(collection_prefix=collection_prefix)
        )
    if name == "milvus":
        return MilvusVectorStore(
            settings=MilvusSettings(collection_prefix=collection_prefix)
        )
    if name == "weaviate":
        return WeaviateVectorStore(
            settings=WeaviateSettings(collection_prefix=collection_prefix)
        )
    raise ValueError(f"Unsupported vector store: {name!r}")
