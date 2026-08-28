"""Pre-resolution entity and relation mentions produced by an Extractor."""

from uuid import UUID

from pydantic import BaseModel


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
    """

    chunk_id: UUID
    label: str
    text: str
    char_start: int
    char_end: int
    confidence: float | None = None


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
