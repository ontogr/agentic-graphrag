"""Source status keeps committed lifecycle states distinct from job state.

Index readiness comes from ``GraphStore.list_indexes``. The status query
returns the lease expiry as epoch milliseconds and the job creation time as
an ISO-8601 string, which the module converts before building the result.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.evidence import SourceState
from agrag.common.data_models.index_record import IndexInfo
from agrag.cypher.schema import fulltext_index_name, vector_index_name
from agrag.evidence.source_status import source_status
from agrag.graphdb.base import GraphStore


_LEASE_EXPIRES_AT_MS = 1893456000000  # 2030-01-01T00:00:00Z

_INDEXES = [
    IndexInfo(
        name=fulltext_index_name(CHUNK_LABEL, ["text"]),
        state="ONLINE",
        population_percent=100.0,
        type="FULLTEXT",
        labels=[CHUNK_LABEL],
        properties=["text"],
    ),
    IndexInfo(
        name=vector_index_name(CHUNK_LABEL, "embedding"),
        state="POPULATING",
        population_percent=42.0,
        type="VECTOR",
        labels=[CHUNK_LABEL],
        properties=["embedding"],
        dimensions=3,
    ),
]


def _store(rows: list[dict[str, object]]) -> AsyncMock:
    store = AsyncMock(spec=GraphStore)
    store.execute_read.return_value = rows
    store.list_indexes.return_value = _INDEXES
    return store


class TestSourceStatus:
    """The typed status reports the source state and index population."""

    async def test_unknown_source_has_no_document_version(self) -> None:
        """An absent key remains unknown while global index state is returned."""
        store = _store([])

        result = await source_status(store, "missing")

        assert result.state is SourceState.UNKNOWN
        assert result.content_hash is None
        assert [index.state for index in result.indexes] == ["ONLINE", "POPULATING"]
        assert result.indexes[1].population_percent == 42.0

    async def test_index_missing_from_listing_reports_missing(self) -> None:
        """An index the store does not list is reported as MISSING."""
        store = _store([])
        store.list_indexes.return_value = _INDEXES[:1]

        result = await source_status(store, "missing")

        assert [index.state for index in result.indexes] == ["ONLINE", "MISSING"]
        assert result.indexes[1].population_percent is None

    @pytest.mark.parametrize(
        ("lease_expired", "expected_state"),
        [(False, SourceState.PENDING), (True, SourceState.FAILED)],
    )
    async def test_incomplete_job_state_tracks_lease(
        self, lease_expired: bool, expected_state: SourceState
    ) -> None:
        """A live lease is pending and an expired lease is failed."""
        created_at = datetime.now(UTC) - timedelta(seconds=120)
        store = _store(
            [
                {
                    "document_exists": True,
                    "job_id": "job-1",
                    "job_status": "pending",
                    "lease_expires_at": _LEASE_EXPIRES_AT_MS,
                    "job_created_at": created_at.isoformat(),
                    "lease_expired": lease_expired,
                    "has_current": True,
                    "complete": True,
                    "content_hash": "abc",
                    "activation_seq": 2,
                    "version_id": "version-2",
                }
            ]
        )

        result = await source_status(store, "key")

        assert result.state is expected_state
        assert result.job_id == "job-1"
        assert result.job_status == "pending"
        assert result.activation_seq == 2
        assert result.version_id == "version-2"
        assert result.job_error == ("job lease expired" if lease_expired else None)
        assert result.lease_expires_at == "2030-01-01T00:00:00+00:00"
        assert result.job_age_seconds is not None
        assert result.job_age_seconds >= 120

    async def test_deleted_source_uses_latest_committed_delete(self) -> None:
        """A delete activation differs from an unknown source."""
        store = _store(
            [
                {
                    "document_exists": True,
                    "last_verb": "delete",
                    "has_current": False,
                    "complete": True,
                    "activation_seq": 3,
                }
            ]
        )

        result = await source_status(store, "deleted")

        assert result.state is SourceState.DELETED
        assert result.activation_seq == 3

    async def test_unstamped_current_chunks_report_failed(self) -> None:
        """A committed chunk without its extraction stamp is not complete."""
        store = _store(
            [
                {
                    "document_exists": True,
                    "has_current": True,
                    "complete": False,
                    "last_verb": "add",
                }
            ]
        )

        result = await source_status(store, "incomplete")

        assert result.state is SourceState.FAILED
