"""Materialized identity clusters for non-destructive entity resolution."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from agrag.common.data_models.data_point import DataPoint
from agrag.common.data_models.graph_record import NodeRecord


RESOLVED_ENTITY_LABEL = "ResolvedEntity"
MATCHES_RELATION = "MATCHES"
RESOLVED_AS_RELATION = "RESOLVED_AS"


class ResolvedEntity(DataPoint):
    """A materialized cluster of entities that refer to the same thing."""

    label: str
    name: str
    properties: dict[str, object] = Field(default_factory=dict)
    member_ids: list[UUID] = Field(default_factory=list)
    embedding: list[float] | None = None
    vector_sync_status: Literal["pending", "synced", "failed"] = "pending"
    vector_sync_error: str | None = None

    @property
    def embedding_text(self) -> str:
        """Return the text used to embed this resolved entity."""
        description = self.properties.get("description")
        return f"{self.name}: {description}" if description else self.name

    def to_node_record(self) -> NodeRecord:
        """Return this resolved entity as a graph write record."""
        properties: dict[str, object] = {
            **self.properties,
            "name": self.name,
            "label": self.label,
            "member_ids": [str(member_id) for member_id in self.member_ids],
            "created_at": self.created_at.isoformat(),
            "vector_sync_status": self.vector_sync_status,
        }
        if self.embedding is not None:
            properties["embedding"] = self.embedding
        if self.vector_sync_error is not None:
            properties["vector_sync_error"] = self.vector_sync_error
        return NodeRecord(
            id=self.id, labels=[RESOLVED_ENTITY_LABEL], properties=properties
        )
