"""Milvus-specific UTF-8 limits, label literals and sorted UUID pagination."""

import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.vector_record import Distance, VectorKind, VectorRecord
from agrag.vectordb.errors import CollectionMismatchError
from agrag.vectordb.milvus import MilvusSettings, MilvusVectorStore


@pytest.fixture
async def milvus_store() -> AsyncIterator[MilvusVectorStore]:
    """Use a unique namespace on the Milvus service selected for this run."""
    if "milvus" not in os.environ.get("AGRAG_TEST_VECTOR_STORES", "").split(","):
        pytest.skip("Milvus was not selected")
    store = MilvusVectorStore(MilvusSettings(collection_prefix=f"test_{uuid4().hex}"))
    await store.initialize()
    try:
        await store.ensure_collection(
            VectorKind.ENTITY, dimensions=2, distance=Distance.COSINE
        )
        yield store
    finally:
        await store.delete_collection(VectorKind.ENTITY)
        await store.close()


class TestMilvusVectorStore:
    """Backend-specific limits preserve the shared vector-store contract."""

    async def test_utf8_truncation_preserves_dense_vector(
        self, milvus_store: MilvusVectorStore
    ) -> None:
        """A split multibyte character cannot break ingestion or dense scoring."""
        from pymilvus import AsyncMilvusClient  # noqa: PLC0415

        record = VectorRecord(
            id=uuid4(), vector=[0.6, 0.8], labels=["Person"], text="x" * 65534 + "é"
        )
        await milvus_store.upsert(VectorKind.ENTITY, [record])
        hits = await milvus_store.search(VectorKind.ENTITY, [0.6, 0.8], limit=1)
        assert [hit.id for hit in hits] == [record.id]
        assert hits[0].score == pytest.approx(1.0, abs=0.001)
        assert record.text.endswith("é")

        client = AsyncMilvusClient(
            uri=milvus_store.settings.uri,
            token=(
                milvus_store.settings.token.get_secret_value()
                if milvus_store.settings.token
                else ""
            ),
        )
        try:
            rows = await client.query(
                milvus_store.collection_name(VectorKind.ENTITY),
                ids=[str(record.id)],
                output_fields=["text"],
                consistency_level="Strong",
            )
            assert rows[0]["text"] == "x" * 65534
        finally:
            await client.close()
        info = await milvus_store.collection_info(VectorKind.ENTITY)
        assert info is not None
        assert info.count == 1

    async def test_label_literals_do_not_widen_filter(
        self, milvus_store: MilvusVectorStore
    ) -> None:
        """Quotes and backslashes remain part of labels on the real server."""
        special = 'quote"slash\\label'
        matching, other = uuid4(), uuid4()
        await milvus_store.upsert(
            VectorKind.ENTITY,
            [
                VectorRecord(
                    id=matching, vector=[1, 0], labels=[special], text="first record"
                ),
                VectorRecord(
                    id=other, vector=[0.8, 0.2], labels=["Person"], text="second record"
                ),
            ],
        )
        hits = await milvus_store.search(
            VectorKind.ENTITY, [1, 0], limit=10, labels=[special]
        )
        assert [hit.id for hit in hits] == [matching]
        assert hits[0].payload == {"labels": [special]}

    async def test_pagination_sorts_before_limiting(
        self, milvus_store: MilvusVectorStore
    ) -> None:
        """Out-of-order inserts cannot skip small UUIDs at a page boundary."""
        ids = [UUID(int=value) for value in (300, 1, 500, 22, 2)]
        await milvus_store.upsert(
            VectorKind.ENTITY,
            [
                VectorRecord(
                    id=record_id, vector=[1, 0], labels=["Person"], text="record"
                )
                for record_id in ids
            ],
        )
        first = await milvus_store.list_ids(VectorKind.ENTITY, limit=2)
        second = await milvus_store.list_ids(
            VectorKind.ENTITY, after=first[-1], limit=2
        )
        third = await milvus_store.list_ids(
            VectorKind.ENTITY, after=second[-1], limit=2
        )
        assert first == [UUID(int=1), UUID(int=2)]
        assert second == [UUID(int=22), UUID(int=300)]
        assert third == [UUID(int=500)]

    async def test_rejects_dense_only_collection(
        self, milvus_store: MilvusVectorStore
    ) -> None:
        """Matching dense settings cannot hide missing labels and BM25 fields."""
        from pymilvus import AsyncMilvusClient  # noqa: PLC0415

        await milvus_store.delete_collection(VectorKind.ENTITY)
        client = AsyncMilvusClient(
            uri=milvus_store.settings.uri,
            token=(
                milvus_store.settings.token.get_secret_value()
                if milvus_store.settings.token
                else ""
            ),
        )
        try:
            await client.create_collection(
                milvus_store.collection_name(VectorKind.ENTITY),
                dimension=2,
                id_type="string",
                max_length=64,
                metric_type="COSINE",
                auto_id=False,
            )
            with pytest.raises(CollectionMismatchError):
                await milvus_store.ensure_collection(
                    VectorKind.ENTITY, dimensions=2, distance=Distance.COSINE
                )
        finally:
            await client.close()

    async def test_hybrid_endpoints_and_filters(
        self, milvus_store: MilvusVectorStore
    ) -> None:
        """Dense-only candidates cannot enter BM25-only results or bypass labels."""
        dense, lexical, excluded = uuid4(), uuid4(), uuid4()
        await milvus_store.upsert(
            VectorKind.ENTITY,
            [
                VectorRecord(id=dense, vector=[1, 0], labels=["Keep"], text="banana"),
                VectorRecord(
                    id=lexical, vector=[0, 1], labels=["Keep"], text="telescope"
                ),
                VectorRecord(
                    id=excluded, vector=[1, 0], labels=["Other"], text="telescope"
                ),
            ],
        )
        sparse_hits = await milvus_store.hybrid_search(
            VectorKind.ENTITY, [1, 0], "telescope", limit=10, alpha=0
        )
        assert {hit.id for hit in sparse_hits} == {lexical, excluded}
        for alpha in (0.0, 0.5, 1.0):
            hits = await milvus_store.hybrid_search(
                VectorKind.ENTITY,
                [1, 0],
                "telescope",
                limit=10,
                alpha=alpha,
                labels=["Keep"],
            )
            if alpha == 0:
                assert [hit.id for hit in hits] == [lexical]
            else:
                assert {hit.id for hit in hits} == {dense, lexical}
                if alpha == 1:
                    assert hits[0].id == dense

    @pytest.mark.parametrize("labels", [["é" * 129], ["Label"] * 4097])
    async def test_rejects_oversized_labels_before_any_write(
        self, milvus_store: MilvusVectorStore, labels: list[str]
    ) -> None:
        """A bad second record cannot partially write a valid first record."""
        records = [
            VectorRecord(id=uuid4(), vector=[1, 0], labels=["Person"], text="valid"),
            VectorRecord(id=uuid4(), vector=[1, 0], labels=labels, text="invalid"),
        ]
        with pytest.raises(ValueError, match="labels"):
            await milvus_store.upsert(VectorKind.ENTITY, records, batch_size=1)
        assert await milvus_store.list_ids(VectorKind.ENTITY) == []
