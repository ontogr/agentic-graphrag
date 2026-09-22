"""Graph storage record shapes for GraphStore.

These are a temporary, minimal stopgap, not the canonical Entity/Relation
domain model resolution will eventually produce. See the future
storage/merge-mechanics work this decouples from.

Pending-visibility convention: a node or edge *created* by an in-flight
Cutover Job carries ``_pending_job_id`` (the job's id) in its properties;
committed data never carries this key. Retrieval query builders exclude
such rows with ``pending_filter_clause``. Vector-store payloads mirror the
tag as an explicit boolean ``_pending`` field, cleared at commit, because
payload filters match on present values rather than key absence.

The tag is written with ``ON CREATE SET``, so a job that writes over a
row that already exists leaves it untagged. Such a row was already
visible before the job started and stays visible; the job's rollback,
which deletes tagged rows, therefore cannot delete data a caller
committed earlier.
"""

from typing import Any, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


PENDING_JOB_ID_PROPERTY = "_pending_job_id"
"""Graph property marking a node or edge as created by an in-flight job.

Carried on every node or edge a Cutover Job creates; committed data and
rows a job only writes over never carry it. Retrieval query builders
exclude rows carrying it, the commit step removes it atomically, and
rollback deletes every row carrying it. Vector-store payloads mirror it
under the same key for commit-time clearing.
"""


class NodeRecord(BaseModel):
    """One graph node, ready to write.

    Attributes:
        id: The node id.
        labels: The node's labels. A node carries every label listed here;
            ``GraphStore.upsert_nodes`` groups records by their full label set
            within a batch, since Cypher requires labels to be literal in the
            query rather than a runtime parameter.
        properties: The node's properties, including an embedding vector under
            whatever key ``GraphStore.ensure_vector_index`` was configured
            with, if native vector search is in use.
    """

    id: UUID
    labels: list[str] = Field(min_length=1)
    properties: dict[str, Any]

    @field_validator("properties")
    @classmethod
    def reject_pending_tag(cls, properties: dict[str, Any]) -> dict[str, Any]:
        """Reject the job-owned tag in external graph records."""
        if PENDING_JOB_ID_PROPERTY in properties:
            raise ValueError(f"{PENDING_JOB_ID_PROPERTY} is reserved")
        return properties


class RelationRecord(BaseModel):
    """One graph relationship, ready to write.

    Attributes:
        id: The relationship id.
        type: The relationship type.
        start_id: The id of the start node.
        end_id: The id of the end node.
        properties: The relationship's properties.
    """

    id: UUID
    type: str
    start_id: UUID
    end_id: UUID
    properties: dict[str, Any]

    @field_validator("properties")
    @classmethod
    def reject_pending_tag(cls, properties: dict[str, Any]) -> dict[str, Any]:
        """Reject the job-owned tag in external graph records."""
        if PENDING_JOB_ID_PROPERTY in properties:
            raise ValueError(f"{PENDING_JOB_ID_PROPERTY} is reserved")
        return properties


class UpsertFailure(BaseModel):
    """One record that failed to write within a bulk upsert call.

    Attributes:
        id: The failed record's own id, as a string (matches the id already
            sent to the backend, not necessarily parseable back to UUID for
            every future backend).
        error_type: The backend exception class name or GraphStore failure label.
        error_message: The backend exception message or failure description.
    """

    id: str
    error_type: str
    error_message: str


class UpsertResult(BaseModel):
    """Outcome of a bulk ``upsert_nodes``/``upsert_relations`` call.

    Attributes:
        written: How many records were written successfully.
        failures: Records that failed, isolated from the rest of the call.
            Empty when every record wrote successfully.
    """

    written: int = 0
    failures: list[UpsertFailure] = Field(default_factory=list)


_RecordT = TypeVar("_RecordT", NodeRecord, RelationRecord)


def tag_pending(record: _RecordT, job_id: UUID | str | None) -> _RecordT:
    """Stamp a write record with the Cutover Job that is writing it.

    The tag reaches the graph only when the write creates its row; the
    upsert queries apply it with ``ON CREATE SET``.

    No-op outside a job, so pipeline stages thread their optional job id
    through this unconditionally instead of branching at every write.

    Args:
        record: The node or relationship record about to be written.
        job_id: The in-flight job's id, or None outside a job.

    Returns:
        The same record, tagged when a job id was given.
    """
    if job_id is not None:
        record.properties[PENDING_JOB_ID_PROPERTY] = str(job_id)
    return record
