"""Graph storage record shapes for GraphStore.

These are a temporary, minimal stopgap, not the canonical Entity and Relation
domain model that resolution will eventually produce. See the future
storage and merge-mechanics work this decouples from.

Pending-visibility convention: a Cutover Job tags each node and edge it
creates with ``_pending_job_id`` (the job id). A job writes only rows it
created. A write that reaches a committed row is not applied: the store
reports that record as unwritten and holds it in a ``DeferredWrites`` list.
The commit transaction replays the list after the job flips to committed, so
a committed row changes only together with the commit. ``GraphStore`` writes
the tag when the caller passes ``pending_job_id`` to an upsert, so records
never carry it and the validators below reject it. Retrieval query builders
exclude tagged rows with ``pending_filter_clause``.

Rollback deletes the rows a job tagged. Committed rows are never tagged by a
job, so rollback cannot delete data committed earlier and leaves those rows
as they were.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


PENDING_JOB_ID_PROPERTY = "_pending_job_id"
"""Graph property marking a node or edge as created by an in-flight job.

Written by ``GraphStore`` on every node or edge a Cutover Job creates. A job
never tags a committed row, so committed data never carries it. Retrieval
query builders exclude rows carrying it, the commit step removes it
atomically, and rollback deletes every row carrying it. Vector-store payloads
hold the job id under the same key.
"""


class NodeRecord(BaseModel):
    """One graph node, ready to write.

    Attributes:
        id: The node id.
        labels: The node labels. A node carries every label listed here.
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


@dataclass
class DeferredWrites:
    """Writes over committed rows, held until the job's commit transaction.

    A job may write only rows it created. A write that reaches a committed
    row is not applied. The store records it here, and the commit transaction
    runs it after the job flips to committed, so a committed row changes
    together with the commit and never before. The list lives in the worker
    process. A crash before the commit transaction rolls the job back, which
    needs nothing from this list, and the commit transaction is atomic.

    Attributes:
        entries: Each deferred ``(query, parameters)`` in write order. Order
            matters: a survivor's text replays before its embedding.
    """

    entries: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def __len__(self) -> int:
        """Return the number of deferred statements."""
        return len(self.entries)

    def add(self, query: str, parameters: Mapping[str, Any]) -> None:
        """Defer one statement whose parameters already carry no job id."""
        self.entries.append((query, dict(parameters)))

    def add_unwritten(
        self,
        query: str,
        records: Sequence[Mapping[str, Any]],
        rows: Sequence[Mapping[str, Any]],
        *,
        require_all: bool = True,
    ) -> int:
        """Defer the records whose result row says ``written`` is false.

        Args:
            query: The batched write query that produced ``rows``.
            records: The ``$records`` the query ran with.
            rows: The rows it returned, each with ``id`` and ``written``.
            require_all: Whether replay must return one row per record. False
                for writes guarded by a text match, where a missing row means
                the guard failed.

        Returns:
            How many records were deferred.
        """
        unwritten = {str(row["id"]) for row in rows if row.get("written") is False}
        deferred = [
            {**record, "pending_job_id": None}
            for record in records
            if str(record["id"]) in unwritten
        ]
        if deferred:
            self.entries.append(
                (query, {"records": deferred, "require_all": require_all})
            )
        return len(deferred)
