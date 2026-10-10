"""Tests for the commit and rollback of staged records in ``VectorStore``."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.vector_record import VectorRecord
from agrag.vectordb.base import VectorStore
from agrag.vectordb.pending import stage_records


class _PagedStore(VectorStore):
    """In-memory store whose scroll honors ``limit`` and never uses offsets."""

    def __init__(self, *, ignore_deletes: bool = False) -> None:
        """Create an empty store."""
        self.records: dict[UUID, VectorRecord] = {}
        self.ignore_deletes = ignore_deletes

    async def initialize(self) -> None:
        """Do nothing."""

    async def ensure_collection(self, *args: Any, **kwargs: Any) -> None:
        """Do nothing."""

    async def collection_exists(self, name: str) -> bool:
        """Report that the collection exists."""
        return True

    async def delete_collection(self, name: str) -> None:
        """Do nothing."""

    async def search(self, *args: Any, **kwargs: Any) -> list[Any]:
        """Return no hits."""
        return []

    async def hybrid_search(self, *args: Any, **kwargs: Any) -> list[Any]:
        """Return no hits."""
        return []

    async def retrieve(self, collection: str, ids: Sequence[UUID]) -> list[Any]:
        """Return no records."""
        return []

    async def count(self, collection: str, **kwargs: Any) -> int:
        """Return zero."""
        return 0

    async def close(self) -> None:
        """Do nothing."""

    async def upsert(
        self,
        collection: str,
        records: Sequence[VectorRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
    ) -> None:
        """Store the records, staged when a job id is given."""
        for record in stage_records(records, pending_job_id):
            self.records[record.id] = record

    async def scroll(
        self,
        collection: str,
        *,
        limit: int = 100,
        page_offset: str | None = None,
        filters: dict[str, Any] | None = None,
        with_vectors: bool = False,
        pending_job_id: UUID | None = None,
    ) -> tuple[list[VectorRecord], str | None]:
        """Return one page; a page offset is an error, as past a result cap."""
        assert page_offset is None
        matches = [
            record
            for record in self.records.values()
            if (
                record.payload.get("_pending_job_id") == str(pending_job_id)
                if pending_job_id is not None
                else not record.payload.get("_pending")
            )
        ]
        return matches[:limit], "next"

    async def delete(self, collection: str, ids: Sequence[UUID]) -> None:
        """Drop the ids unless the store is set to lose deletes."""
        if self.ignore_deletes:
            return
        for record_id in ids:
            self.records.pop(record_id, None)


def _records(count: int) -> list[VectorRecord]:
    """Build records with distinct ids."""
    return [
        VectorRecord(id=uuid4(), vector=[1.0], payload={"n": n}) for n in range(count)
    ]


class TestVectorStorePending:
    """Commit and rollback of staged records."""

    async def test_commit_is_a_no_op_without_staged_records(self) -> None:
        """A second commit after a finished one changes nothing."""
        store = _PagedStore()
        job = uuid4()
        await store.upsert("c", _records(5), pending_job_id=job)
        await store.commit_pending("c", job_id=job)
        before = dict(store.records)

        await store.commit_pending("c", job_id=job)

        assert store.records == before

    @pytest.mark.parametrize("method", ["commit_pending", "delete_pending"])
    async def test_raises_when_deletes_remove_nothing(self, method: str) -> None:
        """A store that drops deletes ends in an error, not an endless loop."""
        store = _PagedStore(ignore_deletes=True)
        job = uuid4()
        await store.upsert("c", _records(3), pending_job_id=job)

        with pytest.raises(RuntimeError, match="removed nothing"):
            await getattr(store, method)("c", job_id=job)
