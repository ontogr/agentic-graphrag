"""Graph storage record shapes for GraphStore.

These are a temporary, minimal stopgap, not the canonical Entity/Relation
domain model resolution will eventually produce. See the future
storage/merge-mechanics work this decouples from.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class NodeRecord(BaseModel):
    """One graph node, ready to write.

    Attributes:
        id: The node id.
        labels: The node's labels.
        properties: The node's properties, including an embedding vector under
            whatever key ``GraphStore.ensure_vector_index`` was configured
            with, if native vector search is in use.
    """

    id: UUID
    labels: list[str]
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
