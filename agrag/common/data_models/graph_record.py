"""Graph storage record shapes for GraphStore.

These are a temporary, minimal stopgap, not the canonical Entity/Relation
domain model resolution will eventually produce. See the future
storage/merge-mechanics work this decouples from.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


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
