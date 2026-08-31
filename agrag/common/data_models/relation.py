"""The canonical, deduped graph relationship that merge mechanics produces."""

from uuid import UUID

from pydantic import Field

from agrag.common.data_models.data_point import DataPoint
from agrag.common.data_models.graph_record import RelationRecord


class Relation(DataPoint):
    """A resolved relationship between two Entity nodes.

    Attributes:
        type: The RelationType label this relationship was resolved as.
        source_id: The id of the source Entity.
        target_id: The id of the target Entity.
        properties: Field-resolved property values.
        source_chunk_ids: Ids of every Chunk a mention contributing to this
            relationship came from. A relationship attested by more than one
            source has more than one id here, rather than existing as
            parallel edges.
    """

    type: str
    source_id: UUID
    target_id: UUID
    properties: dict[str, object] = Field(default_factory=dict)
    source_chunk_ids: list[UUID] = Field(default_factory=list)

    def to_relation_record(self) -> RelationRecord:
        """Return this relationship as a GraphStore write record."""
        properties: dict[str, object] = {
            **self.properties,
            "source_chunk_ids": [str(chunk_id) for chunk_id in self.source_chunk_ids],
            "created_at": self.created_at.isoformat(),
        }
        return RelationRecord(
            id=self.id,
            type=self.type,
            start_id=self.source_id,
            end_id=self.target_id,
            properties=properties,
        )
