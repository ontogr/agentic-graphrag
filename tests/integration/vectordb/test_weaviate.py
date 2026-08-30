"""Integration tests for the Weaviate vector-store backend.

These run against the Docker Compose Weaviate instance from
``docker/docker-compose.ci.yml``. Start it with ``make dev-services-up`` before
running. The ``skipif`` only guards the missing extra; with the extra installed
the tests expect a reachable Weaviate at the default ``WEAVIATE_URL`` in
``custom`` mode.
"""

import importlib.util
from uuid import uuid4

import pytest

from agrag.common.data_models.vector_record import Distance, VectorRecord
from agrag.vectordb import build_vector_store
from agrag.vectordb.errors import CollectionDimensionMismatchError
from agrag.vectordb.settings import WeaviateSettings
from agrag.vectordb.weaviate import WeaviateVectorStore


weaviate_missing = importlib.util.find_spec("weaviate") is None

VECTOR_DIM = 4


@pytest.mark.skipif(weaviate_missing, reason="weaviate-client extra not installed")
class TestWeaviateVectorStoreIntegration:
    """End-to-end behavior against a real Weaviate instance."""

    def _store(self) -> WeaviateVectorStore:
        """Build a store pointed at the local Docker Compose instance."""
        return WeaviateVectorStore(
            settings=WeaviateSettings(mode="custom", url="http://localhost:8080")
        )

    async def test_dense_search_round_trip(self) -> None:
        """Writes and dense-searches synthetic vectors."""
        store = self._store()
        try:
            name = f"Chunks_{uuid4().hex[:8]}"
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
        store = self._store()
        try:
            name = f"Chunks_{uuid4().hex[:8]}"
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
        """Hybrid search fuses dense and keyword matches."""
        store = self._store()
        try:
            name = f"Chunks_{uuid4().hex[:8]}"
            await store.ensure_collection(
                name, dimensions=VECTOR_DIM, distance=Distance.COSINE
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
        store = self._store()
        try:
            name = f"Chunks_{uuid4().hex[:8]}"
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

    async def test_dimension_mismatch_raises(self) -> None:
        """A conflicting vector dimension raises CollectionDimensionMismatchError."""
        store = self._store()
        try:
            name = f"Chunks_{uuid4().hex[:8]}"
            await store.ensure_collection(
                name, dimensions=VECTOR_DIM, distance=Distance.COSINE
            )
            await store.upsert(
                name,
                [VectorRecord(id=uuid4(), vector=[1.0, 0.0, 0.0, 0.0], payload={})],
            )
            with pytest.raises(CollectionDimensionMismatchError):
                await store.ensure_collection(
                    name, dimensions=8, distance=Distance.COSINE
                )
            await store.delete_collection(name)
        finally:
            await store.close()

    async def test_build_from_name(self) -> None:
        """build_vector_store("weaviate") returns a usable store."""
        store = build_vector_store("weaviate")
        try:
            assert isinstance(store, WeaviateVectorStore)
        finally:
            await store.close()
