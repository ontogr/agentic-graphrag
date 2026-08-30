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
