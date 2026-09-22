"""Crash-recoverable state for one add/update/delete_document call."""

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field

from agrag.common.data_models.data_point import DataPoint
from agrag.common.data_models.graph_record import NodeRecord


CUTOVER_JOB_LABEL = "CutoverJob"
CUTOVER_JOB_STATUS_INDEX = "cutover_job_status_index"


class CutoverJobStatus(StrEnum):
    """Lifecycle phase of a Cutover Job."""

    PENDING = "pending"
    COMMITTED = "committed"
    CLEANING = "cleaning"
    DONE = "done"
    ROLLED_BACK = "rolled_back"


class CutoverJob(DataPoint):
    """Crash-recoverable state for one add/update/delete_document call.

    Attributes:
        document_key: The document this job mutates. Unique among
            non-terminal jobs (enforced by a graph constraint plus lease
            fencing, not the constraint alone).
        verb: Which public method created this job.
        status: Current phase, see CutoverJobStatus.
        affected_entity_ids: The snapshot taken before any pending write
            began — the only entities the cleanup phase may touch.
        lease_token: Current lease holder's fencing token.
        lease_expires_at: When the current lease expires.
    """

    document_key: str
    verb: Literal["add", "update", "delete_document"]
    status: CutoverJobStatus
    affected_entity_ids: list[UUID] = Field(default_factory=list)
    lease_token: UUID
    lease_expires_at: datetime

    def to_node_record(self) -> NodeRecord:
        """Return this job as a graph write record."""
        properties: dict[str, object] = {
            "document_key": self.document_key,
            "verb": self.verb,
            "status": self.status.value,
            "affected_entity_ids": [
                str(entity_id) for entity_id in self.affected_entity_ids
            ],
            "lease_token": str(self.lease_token),
            "lease_expires_at": self.lease_expires_at,
            "created_at": self.created_at,
        }
        return NodeRecord(id=self.id, labels=[CUTOVER_JOB_LABEL], properties=properties)
