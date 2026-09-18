"""A non-destructive materialization of a raw entity match component."""

from uuid import NAMESPACE_OID, UUID, uuid5

from pydantic import Field

from agrag.common.data_models.data_point import DataPoint
from agrag.common.data_models.graph_record import NodeRecord


RESOLVED_ENTITY_LABEL = "ResolvedEntity"


def resolved_entity_id(label: str, member_ids: list[UUID]) -> UUID:
    """Return a stable identifier for a label and unordered component members."""
    members = ",".join(sorted(str(member_id) for member_id in member_ids))
    return uuid5(NAMESPACE_OID, f"resolved:{label}:{members}")


class ResolvedEntity(DataPoint):
    """The current materialization of a semantic raw-entity component.

    Attributes:
        label: Domain entity label shared by all raw members.
        name: Canonical component name.
        properties: Canonical component properties.
        member_ids: Stable ids of raw entities represented by this node.
        merge_count: Total mention count represented by the component.
        source_chunk_ids: Provenance chunks across all raw members.
        embedding: Optional vector for user-facing resolved retrieval.
    """

    label: str
    name: str
    properties: dict[str, object] = Field(default_factory=dict)
    member_ids: list[UUID] = Field(min_length=2)
    merge_count: int
    source_chunk_ids: list[UUID] = Field(default_factory=list)
    embedding: list[float] | None = None

    @property
    def embedding_text(self) -> str:
        """Return the text used to embed the resolved component."""
        description = self.properties.get("description")
        if description:
            return f"{self.name}: {description}"
        return self.name

    def to_node_record(self) -> NodeRecord:
        """Return this component materialization as a graph write record."""
        properties: dict[str, object] = {
            **self.properties,
            "name": self.name,
            "domain_label": self.label,
            "member_ids": [str(member_id) for member_id in self.member_ids],
            "component_size": len(self.member_ids),
            "merge_count": self.merge_count,
            "source_chunk_ids": [str(chunk_id) for chunk_id in self.source_chunk_ids],
            "created_at": self.created_at.isoformat(),
        }
        if self.embedding is not None:
            properties["embedding"] = self.embedding
        return NodeRecord(
            id=self.id,
            labels=[RESOLVED_ENTITY_LABEL],
            properties=properties,
        )
