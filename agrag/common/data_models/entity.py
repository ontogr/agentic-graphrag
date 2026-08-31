"""The canonical, resolved graph entity that merge mechanics produces."""

from uuid import UUID

from pydantic import Field

from agrag.common.data_models.data_point import DataPoint
from agrag.common.data_models.graph_record import NodeRecord
from agrag.common.text import normalize_text


class Entity(DataPoint):
    """A resolved entity, assembled from one or more ExtractedEntity mentions.

    Attributes:
        label: The EntityType label this entity was resolved as.
        name: The canonical resolved surface form — field-resolved the same
            way any property is, but kept as its own field rather than
            inside properties, since every entity has one regardless of
            EntityType.properties' schema, and it is what gets embedded
            (embedding_text).
        properties: Field-resolved property values, keyed by the schema's
            declared property names (e.g. "dosage", "description" — whatever
            EntityType.properties for this label declares). Never holds name.
        embedding: The entity's dense vector, once populated by the storage
            stage. None before that point.
        merged_from: Ids of entities absorbed into this one by a tombstone
            merge. Empty for an entity that has never absorbed another.
        merge_count: The total number of source mentions and absorbed
            entities this entity's data was assembled from. Starts at 1.
        source_chunk_ids: Ids of every Chunk a mention contributing to this
            entity's data came from. Each also backs one MENTIONED_IN edge
            from that Chunk to this Entity.
    """

    label: str
    name: str
    properties: dict[str, object] = Field(default_factory=dict)
    embedding: list[float] | None = None
    merged_from: list[UUID] = Field(default_factory=list)
    merge_count: int = 1
    source_chunk_ids: list[UUID] = Field(default_factory=list)

    @property
    def embedding_text(self) -> str:
        """Return the text this entity's embedding is computed from.

        Name alone, or name plus a "description" property when the schema
        declares one — decided once, here, so every embedding call site
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

        (label, normalized name) — the same identity ExactMatch already uses
        in-batch, applied to a persisted store lookup. A derived value, not
        stored redundantly anywhere else on this model; to_node_record()
        computes it fresh from label/name every write, so it can never drift
        from what the fields it's derived from actually say.
        """
        return f"{self.label}:{normalize_text(self.name)}"

    def to_node_record(self) -> NodeRecord:
        """Return this entity as a GraphStore write record.

        Name, merge_key, merged_from, merge_count, and source_chunk_ids are
        flattened into properties as plain JSON-safe values; GraphStore has
        no reason to know these fields are special.
        """
        properties: dict[str, object] = {
            **self.properties,
            "name": self.name,
            "merge_key": self.merge_key,
            "merged_from": [str(entity_id) for entity_id in self.merged_from],
            "merge_count": self.merge_count,
            "source_chunk_ids": [str(chunk_id) for chunk_id in self.source_chunk_ids],
            "created_at": self.created_at.isoformat(),
        }
        if self.embedding is not None:
            properties["embedding"] = self.embedding
        return NodeRecord(id=self.id, labels=[self.label], properties=properties)
