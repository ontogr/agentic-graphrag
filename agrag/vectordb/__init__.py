"""External vector indexes with graph-owned visibility and placement."""

from typing import Callable, Literal

from opentelemetry.trace import Tracer

from agrag.vectordb.base import VectorStore
from agrag.vectordb.errors import (
    CollectionMismatchError,
    VectorPlacementError,
    VectorStoreError,
    VectorStoreMissingExtraError,
)
from agrag.vectordb.milvus import MilvusSettings, MilvusVectorStore
from agrag.vectordb.placement import validate_placement
from agrag.vectordb.qdrant import QdrantSettings, QdrantVectorStore


def _build_qdrant(tracer: Tracer | None = None) -> VectorStore:
    """Construct a Qdrant index from environment-backed settings."""
    return QdrantVectorStore(settings=QdrantSettings(), tracer=tracer)


def _build_milvus(tracer: Tracer | None = None) -> VectorStore:
    """Construct a Milvus index from environment-backed settings."""
    return MilvusVectorStore(settings=MilvusSettings(), tracer=tracer)


_VECTOR_STORE_FACTORIES: dict[str, Callable[..., VectorStore]] = {
    "qdrant": _build_qdrant,
    "milvus": _build_milvus,
}

VectorStoreName = Literal["qdrant", "milvus"]


def build_vector_store(
    value: VectorStoreName | VectorStore, *, tracer: Tracer | None = None
) -> VectorStore:
    """Construct a named vector index or return an existing instance unchanged.

    Args:
        value: A supported backend name or an existing vector store.
        tracer: Forwarded to a newly constructed store. An existing instance's
            tracer is fixed at its own construction.

    Returns:
        A vector store that initializes on first use.

    Raises:
        ValueError: The name is unknown, or tracer accompanies an instance.
    """
    if isinstance(value, VectorStore):
        if tracer is not None:
            raise ValueError(
                "tracer has no effect on an already-constructed VectorStore; "
                "pass it to the store's own constructor instead."
            )
        return value
    try:
        factory = _VECTOR_STORE_FACTORIES[value]
    except KeyError:
        raise ValueError(f"Unknown vector store: {value!r}") from None
    return factory(tracer=tracer)


__all__ = [
    "CollectionMismatchError",
    "MilvusSettings",
    "MilvusVectorStore",
    "QdrantSettings",
    "QdrantVectorStore",
    "VectorPlacementError",
    "VectorStore",
    "VectorStoreError",
    "VectorStoreMissingExtraError",
    "VectorStoreName",
    "build_vector_store",
    "validate_placement",
]
