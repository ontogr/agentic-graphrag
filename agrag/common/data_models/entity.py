"""A permanent mention-level graph node, accumulated by exact-name matching."""

from uuid import UUID

from pydantic import Field

from agrag.common.data_models.data_point import DataPoint
from agrag.common.data_models.graph_record import NodeRecord
from agrag.common.text import normalize_text


class Entity(DataPoint):
    """A permanent mention-level node, never destroyed once written.

    Each Entity is one raw record. Exact-match accumulation only folds a
    new mention into the existing node for its normalized name. Fuzzy,
    embedding, and LLM matches never absorb a node. They persist as
    MATCHES edges with a derived ResolvedEntity instead, so both raw
    records and their relationships survive resolution.

    Attributes:
        label: The EntityType label this entity was resolved as.
        name: The canonical resolved surface form. It is field-resolved the
            same way any property is, but it stays as its own field rather
            than inside properties, since every entity has one regardless of
            EntityType.properties schema. It is what gets embedded
            (embedding_text).
        properties: Field-resolved property values, keyed by the schema
            declared property names (for example "dosage" or "description",
            whatever EntityType.properties for this label declares). Never
            holds name.
        embedding: The entity's dense vector, once populated by the storage
            stage. None before that point.
        merge_count: The total number of source mentions this entity's data
            was assembled from. Starts at 1.
        source_chunk_ids: Ids of every Chunk a mention contributing to this
            entity's data came from. Each also backs one MENTIONED_IN edge
            from that Chunk to this Entity.
    """

    label: str
    name: str
    properties: dict[str, object] = Field(default_factory=dict)
    embedding: list[float] | None = None
    merge_count: int = 1
    source_chunk_ids: list[UUID] = Field(default_factory=list)

    @property
    def embedding_text(self) -> str:
        """Return the text this entity's embedding is computed from.

        Name alone, or name plus a "description" property when the schema
        declares one. Decided once, here, so every embedding call site
        (resolution's future embedding tier, storage-stage population,
        Graph.consolidate()) embeds the same text for the same entity.
        """
        description = self.properties.get("description")
        if description:
            return f"{self.name}: {description}"
        return self.name

    @property
    def merge_key(self) -> str:
        """Return this entity's global exact-match lookup key.

        The key is (label, normalized name). It uses the same identity that
        ExactMatch already uses in-batch, applied to a persisted store lookup.
        A derived value, not stored redundantly anywhere else on this model.
        to_node_record() computes it fresh from label and name on every write,
        so it can never drift from what the fields it's derived from actually say.
        """
        return f"{self.label}:{normalize_text(self.name)}"

    def to_node_record(self) -> NodeRecord:
        """Return this entity as a GraphStore write record.

        Name, merge_key, merge_count, and source_chunk_ids are
        flattened into properties as plain JSON-safe values. GraphStore has
        no reason to know these fields are special.
        """
        properties: dict[str, object] = {
            **self.properties,
            "name": self.name,
            "merge_key": self.merge_key,
            "merge_count": self.merge_count,
            "source_chunk_ids": [str(chunk_id) for chunk_id in self.source_chunk_ids],
            "created_at": self.created_at.isoformat(),
        }
        if self.embedding is not None:
            properties["embedding"] = self.embedding
        return NodeRecord(id=self.id, labels=[self.label], properties=properties)
