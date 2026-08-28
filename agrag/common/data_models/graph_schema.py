"""The GraphSchema contract: entity and relation types extraction validates against."""

from pydantic import BaseModel, Field


class EntityType(BaseModel):
    """One kind of entity a schema recognizes.

    Attributes:
        label: The node label used in the extraction prompt and the graph.
        description: Guidance fed to the extractor prompt or schema builder.
        properties: Property names mapped to a type name, such as ``"str"`` or
            ``"date"``.
        subtypes: Labels that narrow this type. Empty when this type has no subtypes.
    """

    label: str
    description: str
    properties: dict[str, str] = Field(default_factory=dict)
    subtypes: list[str] = Field(default_factory=list)


class RelationType(BaseModel):
    """One kind of relation a schema recognizes.

    Attributes:
        label: The relation label used in the extraction prompt and the graph.
        description: Guidance fed to the extractor prompt or schema builder.
        patterns: Valid (source_label, target_label) pairs for this relation. An
            extraction whose triple is not in this list is dropped at normalize time.
    """

    label: str
    description: str
    patterns: list[tuple[str, str]]


class GraphSchema(BaseModel):
    """A versioned contract of entity and relation types.

    Every extraction call is validated against a GraphSchema; there is no schema-free
    extraction path. Round-trip with ``model_dump(mode="json")``/``model_validate()``.

    Attributes:
        name: A short, unique name for this schema.
        version: The schema version. Bump when types or patterns change.
        entities: The entity types this schema recognizes.
        relations: The relation types this schema recognizes.
    """

    name: str
    version: str
    entities: list[EntityType]
    relations: list[RelationType]


GENERIC = GraphSchema(
    name="generic",
    version="1",
    entities=[
        EntityType(label="Person", description="A named individual."),
        EntityType(label="Organization", description="A company or institution."),
        EntityType(label="Location", description="A place or geographic area."),
        EntityType(label="Event", description="A named occurrence at a time or place."),
        EntityType(label="Product", description="A named product, service, or work."),
    ],
    relations=[
        RelationType(
            label="RELATED_TO",
            description="A generic relationship between two entities.",
            patterns=[
                ("Person", "Person"),
                ("Person", "Organization"),
                ("Organization", "Organization"),
                ("Person", "Location"),
                ("Organization", "Location"),
                ("Person", "Event"),
                ("Organization", "Event"),
                ("Person", "Product"),
                ("Organization", "Product"),
            ],
        ),
    ],
)
