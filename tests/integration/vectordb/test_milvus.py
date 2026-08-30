"""Integration tests for the Milvus vector-store backend.

These run against the Docker Compose Milvus instance from
``docker/docker-compose.ci.yml``. Start it with ``make dev-services-up`` before
running. The ``skipif`` only guards the missing extra; with the extra installed
the tests expect a reachable Milvus at the default ``MILVUS_URI``.
"""

import importlib.util
from uuid import uuid4

import pytest

from agrag.common.data_models.vector_record import Distance, VectorRecord
from agrag.vectordb import build_vector_store
from agrag.vectordb.errors import CollectionDimensionMismatchError
from agrag.vectordb.milvus import MilvusVectorStore


milvus_missing = importlib.util.find_spec("pymilvus") is None

VECTOR_DIM = 4


@pytest.mark.skipif(milvus_missing, reason="pymilvus extra not installed")
class TestMilvusVectorStoreIntegration:
    """End-to-end behavior against a real Milvus instance."""

    async def test_dense_search_round_trip(self) -> None:
        """Writes and dense-searches synthetic vectors."""
        store = build_vector_store("milvus")
        try:
            name = f"chunks_{uuid4().hex[:8]}"
            await store.ensure_collection(
                name, dimensions=VECTOR_DIM, distance=Distance.COSINE
            )
            records = [
                VectorRecord(
                    id=uuid4(), vector=[1.0, 0.0, 0.0, 0.0], payload={"text": "a"}
                ),
                VectorRecord(
                    id=uuid4(), vector=[0.0, 1.0, 0.0, 0.0], payload={"text": "b"}
                ),
            ]
            await store.upsert(name, records)
            hits = await store.search(name, [1.0, 0.0, 0.0, 0.0], limit=2)
            assert len(hits) >= 1
            assert hits[0].payload["text"] == "a"
            await store.delete_collection(name)
        finally:
            await store.close()

    async def test_ensure_collection_is_idempotent(self) -> None:
        """Calling ensure_collection twice does not error."""
        store = build_vector_store("milvus")
        try:
            name = f"chunks_{uuid4().hex[:8]}"
            await store.ensure_collection(
                name, dimensions=VECTOR_DIM, distance=Distance.COSINE
            )
            await store.ensure_collection(
                name, dimensions=VECTOR_DIM, distance=Distance.COSINE
            )
            assert await store.collection_exists(name)
            await store.delete_collection(name)
        finally:
            await store.close()

    async def test_hybrid_search_returns_hits(self) -> None:
        """Hybrid search fuses dense and keyword matches via server-side BM25."""
        store = build_vector_store("milvus")
        try:
            name = f"chunks_{uuid4().hex[:8]}"
            await store.ensure_collection(
                name, dimensions=VECTOR_DIM, distance=Distance.COSINE, hybrid=True
            )
            records = [
                VectorRecord(
                    id=uuid4(),
                    vector=[1.0, 0.0, 0.0, 0.0],
                    payload={"text": "sepsis protocol"},
                ),
                VectorRecord(
                    id=uuid4(),
                    vector=[0.0, 1.0, 0.0, 0.0],
                    payload={"text": "ventilator setup"},
                ),
            ]
            await store.upsert(name, records)
            hits = await store.hybrid_search(
                name, [1.0, 0.0, 0.0, 0.0], "sepsis protocol", limit=2
            )
            assert len(hits) >= 1
            assert hits[0].payload["text"] == "sepsis protocol"
            await store.delete_collection(name)
        finally:
            await store.close()

    async def test_upsert_overwrites_existing_vector(self) -> None:
        """Writing the same id twice replaces the vector and payload, not adds."""
        store = build_vector_store("milvus")
        try:
            name = f"chunks_{uuid4().hex[:8]}"
            await store.ensure_collection(
                name, dimensions=VECTOR_DIM, distance=Distance.COSINE
            )
            record_id = uuid4()
            await store.upsert(
                name,
                [
                    VectorRecord(
                        id=record_id,
                        vector=[1.0, 0.0, 0.0, 0.0],
                        payload={"text": "old"},
                    )
                ],
            )
            await store.upsert(
                name,
                [
                    VectorRecord(
                        id=record_id,
                        vector=[0.0, 1.0, 0.0, 0.0],
                        payload={"text": "new"},
                    )
                ],
            )
            assert await store.count(name) == 1
            [record] = await store.retrieve(name, [record_id])
            assert record.payload["text"] == "new"
            assert record.vector == pytest.approx([0.0, 1.0, 0.0, 0.0])
            await store.delete_collection(name)
        finally:
            await store.close()

    async def test_scalar_and_list_filters(self) -> None:
        """Payload filters narrow search, hybrid_search, scroll, and count."""
        store = build_vector_store("milvus")
        try:
            name = f"chunks_{uuid4().hex[:8]}"
            await store.ensure_collection(
                name, dimensions=VECTOR_DIM, distance=Distance.COSINE, hybrid=True
            )
            matching = VectorRecord(
                id=uuid4(),
                vector=[1.0, 0.0, 0.0, 0.0],
                payload={"text": "sepsis protocol", "kind": "doc"},
            )
            other = VectorRecord(
                id=uuid4(),
                vector=[0.0, 1.0, 0.0, 0.0],
                payload={"text": "ventilator setup", "kind": "note"},
            )
            await store.upsert(name, [matching, other])

            scalar_filter = {"kind": "doc"}
            search_hits = await store.search(
                name, [1.0, 0.0, 0.0, 0.0], limit=2, filters=scalar_filter
            )
            assert {h.id for h in search_hits} == {matching.id}

            hybrid_hits = await store.hybrid_search(
                name,
                [1.0, 0.0, 0.0, 0.0],
                "sepsis protocol",
                limit=2,
                filters=scalar_filter,
            )
            assert {h.id for h in hybrid_hits} == {matching.id}

            records, _ = await store.scroll(name, filters=scalar_filter)
            assert {r.id for r in records} == {matching.id}

            assert await store.count(name, filters=scalar_filter) == 1

            list_filter = {"kind": ["doc", "note"]}
            assert await store.count(name, filters=list_filter) == 2

            await store.delete_collection(name)
        finally:
            await store.close()

    async def test_dimension_mismatch_raises(self) -> None:
        """A conflicting dimension raises CollectionDimensionMismatchError."""
        store = build_vector_store("milvus")
        try:
            name = f"chunks_{uuid4().hex[:8]}"
            await store.ensure_collection(
                name, dimensions=VECTOR_DIM, distance=Distance.COSINE
            )
            with pytest.raises(CollectionDimensionMismatchError):
                await store.ensure_collection(
                    name, dimensions=8, distance=Distance.COSINE
                )
            await store.delete_collection(name)
        finally:
            await store.close()

    async def test_build_from_name(self) -> None:
        """build_vector_store("milvus") returns a usable store."""
        store = build_vector_store("milvus")
        try:
            assert isinstance(store, MilvusVectorStore)
        finally:
            await store.close()
