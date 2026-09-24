"""Tests for the CutoverJob crash-recovery state model.

Covers the node-record shape the job persistence queries write: every
field the lease protocol needs is present under a stable key, and lease
times retain their native temporal type for Neo4j comparisons.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from agrag.common.data_models.cutover_job import (
    CUTOVER_JOB_LABEL,
    CutoverJob,
    CutoverJobStatus,
)


class TestCutoverJob:
    """CutoverJob node-record shape."""

    def test_to_node_record_carries_lease_state(self) -> None:
        """The record carries every field the lease protocol needs."""
        job_id = uuid4()
        token = uuid4()
        affected = [uuid4()]
        expires = datetime.now(UTC) + timedelta(seconds=60)
        job = CutoverJob(
            id=job_id,
            document_key="doc",
            verb="update",
            status=CutoverJobStatus.PENDING,
            affected_entity_ids=affected,
            lease_token=token,
            lease_expires_at=expires,
        )
        record = job.to_node_record()
        assert record.id == job_id
        assert record.labels == [CUTOVER_JOB_LABEL]
        assert record.properties == {
            "document_key": "doc",
            "verb": "update",
            "status": "pending",
            "affected_entity_ids": [str(affected[0])],
            "lease_token": str(token),
            "lease_expires_at": expires,
            "created_at": job.created_at,
        }
