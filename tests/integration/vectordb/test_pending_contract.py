"""Pending-record contract that every VectorStore backend must meet.

Run against the Docker Compose backends from ``docker/docker-compose.ci.yml``
(``make dev-services-up``).
"""

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from agrag.common.data_models.vector_record import Distance, VectorRecord
from agrag.vectordb import VectorStoreName, build_vector_store
from agrag.vectordb.base import VectorStore


DIM = 4
BACKENDS: list[VectorStoreName] = ["qdrant", "weaviate", "milvus"]
EXTRA = {"count": 7, "tags": ["a", "b"]}


def _record(text: str, vector: list[float], record_id: UUID | None = None):
    """Build one record with a label, text and extra payload fields."""
    return VectorRecord(
        id=record_id or uuid4(),
        vector=vector,
        payload={"label": "Person", "text": text, **EXTRA},
    )


async def _committed_texts(store: VectorStore, name: str, query: str) -> set[str]:
    """Return the text of every record a hybrid search can see."""
    hits = await store.hybrid_search(
        name, [1.0, 0.0, 0.0, 0.0], query, limit=500, alpha=0.5
    )
    return {str(hit.payload["text"]) for hit in hits}


@pytest_asyncio.fixture(params=BACKENDS)
async def collection(request: pytest.FixtureRequest) -> AsyncIterator[tuple]:
    """Yield a store and a fresh hybrid collection, dropped afterwards."""
    store = build_vector_store(request.param)
    name = f"pending_{uuid4().hex[:8]}"
    try:
        await store.initialize()
        await store.ensure_collection(
            name, dimensions=DIM, distance=Distance.COSINE, hybrid=True
        )
        yield store, name
    finally:
        try:
            await store.delete_collection(name)
        finally:
            await store.close()


class TestPendingContract:
    """Staged records stay hidden until commit, whatever the backend."""

    async def test_staged_records_are_hidden_until_commit(
        self, collection: tuple[VectorStore, str]
    ) -> None:
        """Commit makes staged records searchable under their real ids."""
        store, name = collection
        job = uuid4()
        committed = _record("alpha committed", [1.0, 0.0, 0.0, 0.0])
        staged = _record("zebra staged", [0.0, 1.0, 0.0, 0.0])
        await store.upsert(name, [committed])
        await store.upsert(name, [staged], pending_job_id=job)

        assert await store.count(name) == 1
        assert await store.count(name, pending_job_id=job) == 1
        assert await _committed_texts(store, name, "zebra") == {"alpha committed"}
        dense = await store.search(name, [0.0, 1.0, 0.0, 0.0], limit=10)
        assert staged.id not in {hit.id for hit in dense}
        visible, _ = await store.scroll(name, limit=100)
        assert {record.payload["text"] for record in visible} == {"alpha committed"}

        await store.commit_pending(name, job_id=job)

        assert await store.count(name, pending_job_id=job) == 0
        assert await store.count(name) == 2
        hits = await store.hybrid_search(
            name, [0.0, 0.0, 0.0, 1.0], "zebra", limit=5, alpha=0.0
        )
        assert [hit.id for hit in hits][:1] == [staged.id]
        (stored,) = await store.retrieve(name, [staged.id])
        assert stored.payload["text"] == "zebra staged"
        assert stored.payload["count"] == EXTRA["count"]
        assert stored.payload["tags"] == EXTRA["tags"]
        assert stored.payload.get("_pending_job_id") is None
        assert stored.payload.get("_target_id") is None
        assert stored.vector == pytest.approx(staged.vector)

    async def test_commit_and_rollback_handle_more_than_one_page(
        self, collection: tuple[VectorStore, str]
    ) -> None:
        """A job larger than one scroll page commits or rolls back whole."""
        store, name = collection
        committing, rolling_back = uuid4(), uuid4()
        await store.upsert(
            name,
            [_record(f"keep {i}", [1.0, 0.0, 0.0, 1.0]) for i in range(250)],
            pending_job_id=committing,
        )
        await store.upsert(
            name,
            [_record(f"drop {i}", [1.0, 0.0, 1.0, 0.0]) for i in range(250)],
            pending_job_id=rolling_back,
        )

        await store.commit_pending(name, job_id=committing)
        await store.delete_pending(name, job_id=rolling_back)

        assert await store.count(name, pending_job_id=committing) == 0
        assert await store.count(name, pending_job_id=rolling_back) == 0
        assert await store.count(name) == 250

    async def test_rollback_keeps_the_committed_record_with_the_same_id(
        self, collection: tuple[VectorStore, str]
    ) -> None:
        """A staged rewrite hides nothing and a rollback restores nothing."""
        store, name = collection
        job = uuid4()
        original = _record("overwrite original", [1.0, 0.0, 0.0, 0.0])
        rewrite = _record(
            "overwrite rewritten", [1.0, 0.0, 0.0, 0.0], record_id=original.id
        )
        await store.upsert(name, [original])
        await store.upsert(name, [rewrite], pending_job_id=job)

        assert await _committed_texts(store, name, "overwrite") == {
            "overwrite original"
        }

        await store.delete_pending(name, job_id=job)

        assert await _committed_texts(store, name, "overwrite") == {
            "overwrite original"
        }
        assert await store.count(name, pending_job_id=job) == 0

    async def test_commit_replaces_the_committed_record_with_the_same_id(
        self, collection: tuple[VectorStore, str]
    ) -> None:
        """Commit leaves one record per id, holding the staged content."""
        store, name = collection
        job = uuid4()
        original = _record("replace original", [1.0, 0.0, 0.0, 0.0])
        rewrite = _record(
            "replace rewritten", [1.0, 0.0, 0.0, 0.0], record_id=original.id
        )
        await store.upsert(name, [original])
        await store.upsert(name, [rewrite], pending_job_id=job)

        await store.commit_pending(name, job_id=job)

        assert await store.count(name) == 1
        assert await _committed_texts(store, name, "replace") == {"replace rewritten"}
