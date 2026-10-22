"""Weaviate-specific persistence and multi-page UUID ordering on a real server."""

import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.vector_record import Distance, VectorKind, VectorRecord
from agrag.vectordb.errors import CollectionMismatchError
from agrag.vectordb.weaviate import WeaviateSettings, WeaviateVectorStore


@pytest.fixture
async def weaviate_store() -> AsyncIterator[WeaviateVectorStore]:
    """Give each test isolated collections and remove them afterwards."""
    if "weaviate" not in os.getenv("AGRAG_TEST_VECTOR_STORES", "fake").split(","):
        pytest.skip("Weaviate is not selected")
    store = WeaviateVectorStore(
        settings=WeaviateSettings(
            collection_prefix=f"test_{uuid4().hex}",
        )
    )
    await store.initialize()
    try:
        yield store
    finally:
        try:
            for kind in VectorKind:
                await store.delete_collection(kind)
        finally:
            await store.close()


class TestWeaviateVectorStore:
    """Collection metadata survives reconnects and UUID pages remain ordered."""

    async def test_empty_collection_reopen_rejects_dimension_change(
        self,
        weaviate_store: WeaviateVectorStore,
    ) -> None:
        """Dimension validation does not depend on any vector-bearing object."""
        await weaviate_store.ensure_collection(
            VectorKind.CHUNK,
            dimensions=3,
            distance=Distance.COSINE,
        )
        await weaviate_store.close()
        await weaviate_store.initialize()
        info = await weaviate_store.collection_info(VectorKind.CHUNK)
        assert info is not None
        assert (info.dimensions, info.distance, info.count) == (3, Distance.COSINE, 0)
        with pytest.raises(CollectionMismatchError):
            await weaviate_store.ensure_collection(
                VectorKind.CHUNK,
                dimensions=4,
                distance=Distance.COSINE,
            )

    async def test_keyset_pages_across_server_scan_boundary(
        self,
        weaviate_store: WeaviateVectorStore,
    ) -> None:
        """An exclusive cursor need not itself identify an existing object."""
        await weaviate_store.ensure_collection(
            VectorKind.ENTITY,
            dimensions=2,
            distance=Distance.EUCLID,
        )
        ids = [UUID(int=2 * index) for index in range(1, 1108)]
        await weaviate_store.upsert(
            VectorKind.ENTITY,
            [
                VectorRecord(
                    id=id_, vector=[0.4, 0.8], labels=["Entity"], text="record"
                )
                for id_ in reversed(ids)
            ],
        )
        page = await weaviate_store.list_ids(
            VectorKind.ENTITY,
            after=UUID(int=1999),
            limit=7,
        )
        assert page == [UUID(int=value) for value in range(2000, 2014, 2)]
        next_page = await weaviate_store.list_ids(
            VectorKind.ENTITY,
            after=page[-1],
            limit=3,
        )
        assert next_page == [UUID(int=2014), UUID(int=2016), UUID(int=2018)]
