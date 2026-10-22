"""Read the committed lifecycle and index state of a document source."""

from datetime import UTC, datetime
from typing import Any

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.evidence import (
    SourceIndexStatus,
    SourceState,
    SourceStatus,
)
from agrag.cypher.documents import source_status_query
from agrag.cypher.schema import fulltext_index_name, vector_index_name
from agrag.graphdb.base import GraphStore


_INDEXES = (
    fulltext_index_name(CHUNK_LABEL, ["text"]),
    vector_index_name(CHUNK_LABEL, "embedding"),
)


async def source_status(store: GraphStore, document_key: str) -> SourceStatus:
    """Return committed version, job and index state for one document key.

    An expired incomplete job is reported as failed. An active job is reported
    as pending, while deleted and unknown keys remain distinct.

    Args:
        store: The graph store to read.
        document_key: Stable key of the source.

    Returns:
        Source state with the current activation, job lease and index status.
    """
    rows = await store.execute_read(
        source_status_query(), {"document_key": document_key}
    )
    indexes = await _source_index_statuses(store)
    if not rows:
        return SourceStatus(
            document_key=document_key, state=SourceState.UNKNOWN, indexes=indexes
        )

    row = rows[0]
    job_status = row.get("job_status")
    lease_expires_at = _lease_expiry_iso(row.get("lease_expires_at"))
    if not row.get("document_exists") and job_status is None:
        state = SourceState.UNKNOWN
    elif job_status is not None:
        state = (
            SourceState.FAILED
            if lease_expires_at is None or _lease_expired(row)
            else SourceState.PENDING
        )
    elif row.get("has_current") and row.get("complete"):
        state = SourceState.CURRENT
    elif row.get("last_verb") == "delete":
        state = SourceState.DELETED
    else:
        state = SourceState.FAILED

    return SourceStatus(
        document_key=document_key,
        state=state,
        content_hash=(
            row.get("content_hash") if state is not SourceState.DELETED else None
        ),
        activation_seq=row.get("activation_seq"),
        version_id=row.get("version_id"),
        job_id=row.get("job_id"),
        job_status=job_status,
        lease_expires_at=lease_expires_at,
        job_age_seconds=_job_age_seconds(row.get("job_created_at")),
        job_error=row.get("job_error")
        or (
            "job lease expired"
            if state is SourceState.FAILED and job_status is not None
            else None
        ),
        indexes=indexes,
    )


async def _source_index_statuses(store: GraphStore) -> list[SourceIndexStatus]:
    """Read readiness and population progress for source search indexes.

    An index that the store does not list is reported as ``MISSING``.
    """
    found = {index.name: index for index in await store.list_indexes()}
    statuses: list[SourceIndexStatus] = []
    for name in _INDEXES:
        index = found.get(name)
        if index is None:
            statuses.append(
                SourceIndexStatus(name=name, state="MISSING", population_percent=None)
            )
            continue
        statuses.append(
            SourceIndexStatus(
                name=name,
                state=index.state,
                population_percent=index.population_percent,
            )
        )
    return statuses


def _lease_expired(row: dict[str, Any]) -> bool:
    """Read the job lease expiry flag returned by the status query."""
    return bool(row.get("lease_expired"))


def _lease_expiry_iso(epoch_ms: int | None) -> str | None:
    """Render a lease expiry in epoch milliseconds as an ISO-8601 UTC string."""
    if epoch_ms is None:
        return None
    return datetime.fromtimestamp(epoch_ms / 1000, UTC).isoformat()


def _job_age_seconds(created_at: str | None) -> float | None:
    """Return the seconds elapsed since a job's ISO-8601 ``created_at``."""
    if created_at is None:
        return None
    started = datetime.fromisoformat(created_at)
    return (datetime.now(UTC) - started).total_seconds()
