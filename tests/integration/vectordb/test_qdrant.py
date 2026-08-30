"""Integration tests for the Qdrant vector-store backend.

These run against the Docker Compose Qdrant instance from
``docker/docker-compose.ci.yml``. Start it with ``make dev-services-up`` before
running. The ``skipif`` only guards the missing extra; with the extra installed
the tests expect a reachable Qdrant at the default ``QDRANT_URL``.
"""

import importlib.util
from uuid import uuid4

import pytest
from qdrant_client.http.exceptions import UnexpectedResponse

from agrag.common.data_models.vector_record import Distance, VectorRecord
from agrag.vectordb import build_vector_store
from agrag.vectordb.errors import CollectionDimensionMismatchError, VectorStoreError
from agrag.vectordb.qdrant import QdrantVectorStore
from agrag.vectordb.settings import QdrantSettings
from tests.integration._vector_hit import assert_is_usable_vector_hit


qdrant_missing = importlib.util.find_spec("qdrant_client") is None

VECTOR_DIM = 4


@pytest.mark.skipif(qdrant_missing, reason="qdrant-client extra not installed")
class TestQdrantVectorStoreIntegration:
    """End-to-end behavior against a real Qdrant instance."""

    async def test_dense_search_round_trip(self) -> None:
        """Writes and dense-searches synthetic vectors."""
        store = build_vector_store("qdrant")
        try:
            await store.initialize()
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
            assert_is_usable_vector_hit(
                hits[0], expected_id=records[0].id, expected_text="a"
            )
            await store.delete_collection(name)
        finally:
            await store.close()

    async def test_ensure_collection_is_idempotent(self) -> None:
        """Calling ensure_collection twice does not error."""
        store = build_vector_store("qdrant")
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

    async def test_dimension_mismatch_raises(self) -> None:
        """A conflicting dimension raises CollectionDimensionMismatchError."""
        store = build_vector_store("qdrant")
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

    async def test_hybrid_search_returns_hits(self) -> None:
        """Hybrid search fuses dense and keyword matches."""
        store = build_vector_store("qdrant")
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

    async def test_ensure_collection_rejects_hybrid_upgrade_of_dense_collection(
        self,
    ) -> None:
        """A dense collection cannot be upgraded to hybrid in place.

        Upgrading in place would leave existing records without a sparse
        vector, so they would never surface in keyword search. The caller
        needs a new collection instead.
        """
        store = build_vector_store("qdrant")
        try:
            name = f"chunks_{uuid4().hex[:8]}"
            await store.ensure_collection(
                name, dimensions=VECTOR_DIM, distance=Distance.COSINE
            )
            with pytest.raises(VectorStoreError):
                await store.ensure_collection(
                    name, dimensions=VECTOR_DIM, distance=Distance.COSINE, hybrid=True
                )
            await store.delete_collection(name)
        finally:
            await store.close()

    async def test_initialize_wrong_api_key_raises(self) -> None:
        """A wrong API key fails promptly on initialize."""
        store = QdrantVectorStore(settings=QdrantSettings(api_key="not-a-real-key"))
        try:
            with pytest.raises(UnexpectedResponse):
                await store.initialize()
        finally:
            await store.close()
