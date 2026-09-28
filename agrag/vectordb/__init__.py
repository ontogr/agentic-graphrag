"""Vector storage backends and the build shortcut."""

from typing import Callable, Literal

from opentelemetry.trace import Tracer

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


def _build_qdrant(tracer: Tracer | None = None) -> VectorStore:
    """Build a Qdrant vector store with default settings."""
    return QdrantVectorStore(settings=QdrantSettings(), tracer=tracer)


def _build_weaviate(tracer: Tracer | None = None) -> VectorStore:
    """Build a Weaviate vector store with default settings."""
    return WeaviateVectorStore(settings=WeaviateSettings(), tracer=tracer)


def _build_milvus(tracer: Tracer | None = None) -> VectorStore:
    """Build a Milvus vector store with default settings."""
    return MilvusVectorStore(settings=MilvusSettings(), tracer=tracer)


_VECTOR_STORE_FACTORIES: dict[str, Callable[..., VectorStore]] = {
    "qdrant": _build_qdrant,
    "weaviate": _build_weaviate,
    "milvus": _build_milvus,
}


VectorStoreName = Literal["qdrant", "weaviate", "milvus"]


def build_vector_store(
    value: VectorStoreName | VectorStore, *, tracer: Tracer | None = None
) -> VectorStore:
    """Build a vector store from a backend name, or return one unchanged.

    Args:
        value: ``"qdrant"`` or ``"weaviate"``, or an already-constructed
            ``VectorStore`` for full control over settings.
        tracer: Passed to the newly-built store. Not valid together with an
            already-constructed ``value`` -- that instance's tracer, if any,
            was already fixed at its own construction.

    Returns:
        A ready-to-use vector store.

    Raises:
        ValueError: ``tracer`` is given together with an already-constructed
            ``value``.
    """
    if isinstance(value, VectorStore):
        if tracer is not None:
            raise ValueError(
                "tracer has no effect on an already-constructed VectorStore; "
                "pass it to the store's own constructor instead."
            )
        return value
    return _VECTOR_STORE_FACTORIES[value](tracer=tracer)


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
