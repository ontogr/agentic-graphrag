"""Vector storage backends and the build shortcut."""

from typing import Callable, Literal

from agrag.vectordb.base import VectorStore
from agrag.vectordb.errors import (
    CollectionDimensionMismatchError,
    VectorStoreError,
    VectorStoreMissingExtraError,
)
from agrag.vectordb.milvus import MilvusVectorStore
from agrag.vectordb.qdrant import QdrantVectorStore
from agrag.vectordb.settings import MilvusSettings, QdrantSettings, WeaviateSettings
from agrag.vectordb.weaviate import WeaviateVectorStore


def _build_qdrant() -> VectorStore:
    """Build a Qdrant vector store with default settings."""
    return QdrantVectorStore(settings=QdrantSettings())


def _build_weaviate() -> VectorStore:
    """Build a Weaviate vector store with default settings."""
    return WeaviateVectorStore(settings=WeaviateSettings())


def _build_milvus() -> VectorStore:
    """Build a Milvus vector store with default settings."""
    return MilvusVectorStore(settings=MilvusSettings())


_VECTOR_STORE_FACTORIES: dict[str, Callable[[], VectorStore]] = {
    "qdrant": _build_qdrant,
    "weaviate": _build_weaviate,
    "milvus": _build_milvus,
}


VectorStoreName = Literal["qdrant", "weaviate", "milvus"]


def build_vector_store(value: VectorStoreName | VectorStore) -> VectorStore:
    """Build a vector store from a backend name, or return one unchanged.

    Args:
        value: ``"qdrant"`` or ``"weaviate"``, or an already-constructed
            ``VectorStore`` for full control over settings.

    Returns:
        A ready-to-use vector store.
    """
    if isinstance(value, VectorStore):
        return value
    return _VECTOR_STORE_FACTORIES[value]()


__all__ = [
    "CollectionDimensionMismatchError",
    "MilvusSettings",
    "MilvusVectorStore",
    "QdrantSettings",
    "QdrantVectorStore",
    "VectorStore",
    "VectorStoreError",
    "VectorStoreMissingExtraError",
    "WeaviateSettings",
    "WeaviateVectorStore",
    "build_vector_store",
]
