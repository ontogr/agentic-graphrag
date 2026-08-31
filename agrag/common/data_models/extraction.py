"""Pre-resolution entity and relation mentions produced by an Extractor."""

from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ExtractedEntity(BaseModel):
    """One entity mention found in a single Chunk.

    Not a graph node: this has no id and no canonical identity. Resolution decides
    which ExtractedEntity mentions refer to the same real-world thing.

    Attributes:
        chunk_id: The id of the Chunk this mention came from.
        label: The EntityType label this mention was extracted as.
        text: The mention's surface text.
        char_start: The start character offset within the chunk's text.
        char_end: The end character offset within the chunk's text.
        confidence: The extractor's confidence in this mention, when available.
        properties: Schema-declared property values this mention carries,
            keyed by property name. Empty for an extractor that only reports
            spans -- normalize_extraction_result drops any key the schema
            does not declare for this mention's label.
    """

    chunk_id: UUID
    label: str
    text: str
    char_start: int
    char_end: int
    confidence: float | None = None
    properties: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_span(self) -> "ExtractedEntity":
        """Reject negative offsets and reversed or zero-length spans."""
        if self.char_start < 0:
            raise ValueError(f"char_start must be >= 0, got {self.char_start}")
        if self.char_end <= self.char_start:
            raise ValueError(
                f"char_end ({self.char_end}) must be > char_start ({self.char_start})"
            )
        return self


class ExtractedRelation(BaseModel):
    """One relation mention between two ExtractedEntity mentions in one Chunk.

    Attributes:
        chunk_id: The id of the Chunk this mention came from.
        label: The RelationType label this mention was extracted as.
        source_index: Index of the source entity in the same ExtractionResult.entities.
        target_index: Index of the target entity in the same ExtractionResult.entities.
        confidence: The extractor's confidence in this mention, when available.
    """

    chunk_id: UUID
    label: str
    source_index: int
    target_index: int
    confidence: float | None = None

    @model_validator(mode="after")
    def _validate_indices(self) -> "ExtractedRelation":
        """Reject negative indices. Bounds checking is deferred to ExtractionResult."""
        if self.source_index < 0:
            raise ValueError(f"source_index must be >= 0, got {self.source_index}")
        if self.target_index < 0:
            raise ValueError(f"target_index must be >= 0, got {self.target_index}")
        if self.source_index == self.target_index:
            raise ValueError("source_index and target_index must differ")
        return self


class ExtractionResult(BaseModel):
    """The entities and relations one Extractor call found in one Chunk.

    Attributes:
        entities: The mentions found, in extraction order.
        relations: The relation mentions found, referencing entities by index.
        extractor_name: Which Extractor produced this result. Set by the Extractor
            itself; useful for provenance when a EscalatingExtractor escalated.
    """

    entities: list[ExtractedEntity]
    relations: list[ExtractedRelation]
    extractor_name: str

    @model_validator(mode="after")
    def _validate_relation_bounds(self) -> "ExtractionResult":
        """Reject relations whose endpoints index outside the entity list."""
        entity_count = len(self.entities)
        for rel in self.relations:
            if rel.source_index >= entity_count:
                raise ValueError(
                    f"source_index {rel.source_index} >= entity count {entity_count}"
                )
            if rel.target_index >= entity_count:
                raise ValueError(
                    f"target_index {rel.target_index} >= entity count {entity_count}"
                )
        return self
