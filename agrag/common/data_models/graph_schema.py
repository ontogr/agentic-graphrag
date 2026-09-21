"""The GraphSchema contract: entity and relation types extraction validates against."""

from pydantic import BaseModel, Field, model_validator


# Payload keys every mirrored entity embedding carries: the graph label a
# SearchFilters label filter matches on, and the embedding text the backends
# keyword-index. An entity property with one of these names would overwrite
# that key in the VectorStore payload while the GraphStore-native path keeps
# it as an ordinary node property, so the two retrieval paths would disagree.
_RESERVED_ENTITY_PROPERTY_NAMES = frozenset({"label", "text"})


def _format_patterns(patterns: list[tuple[str, str]]) -> str:
    """Render relation patterns as a comma-separated (source, target) list."""
    return ", ".join(f"({source}, {target})" for source, target in patterns)


class EntityType(BaseModel):
    """One kind of entity a schema recognizes.

    Attributes:
        label: The node label used in the extraction prompt and the graph.
        description: Guidance fed to the extractor prompt or schema builder.
        properties: Property names mapped to a type name, such as ``"str"`` or
            ``"date"``. ``label`` and ``text`` are rejected, since both are
            vector payload keys retrieval filtering and keyword search use.
        subtypes: Labels that narrow this type. Empty when this type has no subtypes.
    """

    label: str
    description: str
    properties: dict[str, str] = Field(default_factory=dict)
    subtypes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _reject_reserved_property_names(self) -> "EntityType":
        """Reject property names that collide with vector payload keys.

        Enforced on every construction, including ``model_validate()`` of a
        schema dumped before this check existed: a schema that declares one
        of these names must be migrated rather than quietly accepted. The
        message names the fix so that migration is unambiguous.
        """
        reserved = sorted(_RESERVED_ENTITY_PROPERTY_NAMES & self.properties.keys())
        if reserved:
            raise ValueError(
                f"Entity type '{self.label}' declares reserved property "
                f"name(s) {reserved}; "
                f"{sorted(_RESERVED_ENTITY_PROPERTY_NAMES)} are vector payload "
                f"keys used for retrieval filtering and keyword search. "
                f"Rename or remove those property names in the schema."
            )
        return self


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
    A schema declaring an entity property name the vector payload reserves fails that
    validation, so a payload written before the check existed must be migrated before
    it loads again. See ``EntityType.properties``.

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

    @model_validator(mode="after")
    def _validate_patterns(self) -> "GraphSchema":
        """Reject relation patterns whose endpoints are not declared entities."""
        entity_labels = {e.label for e in self.entities}
        for rel in self.relations:
            for source, target in rel.patterns:
                if source not in entity_labels:
                    raise ValueError(
                        f"Relation '{rel.label}' pattern source '{source}' "
                        f"is not a declared entity"
                    )
                if target not in entity_labels:
                    raise ValueError(
                        f"Relation '{rel.label}' pattern target '{target}' "
                        f"is not a declared entity"
                    )
        return self

    def to_prompt_description(self) -> str:
        """Serialize this schema in full for an LLM prompt.

        Every entity type's label, description, declared properties, and
        subtypes are listed, followed by every relation type's label,
        description, and valid (source, target) patterns. Use
        :meth:`to_compact_summary` instead when prompt space is tight.

        Returns:
            A plain-text schema description, one fact per line.
        """
        lines = [f"Schema {self.name} (version {self.version})", "Entity types:"]
        for entity in self.entities:
            lines.append(f"- {entity.label}: {entity.description}")
            if entity.properties:
                declared = ", ".join(
                    f"{name}: {type_name}"
                    for name, type_name in entity.properties.items()
                )
                lines.append(f"  properties: {declared}")
            if entity.subtypes:
                lines.append(f"  subtypes: {', '.join(entity.subtypes)}")
        lines.append("Relation types:")
        if not self.relations:
            lines.append("(none)")
        for relation in self.relations:
            lines.append(f"- {relation.label}: {relation.description}")
            patterns = _format_patterns(relation.patterns) or "(none)"
            lines.append(f"  valid patterns: {patterns}")
        return "\n".join(lines)

    def to_compact_summary(self) -> str:
        """Serialize only entity labels and relation patterns for a prompt.

        Descriptions, properties, and subtypes are omitted, so this is the
        shape to inject where prompt space is tight.
        :meth:`to_prompt_description` carries the same labels with their
        full detail.

        Returns:
            A plain-text summary of entity labels and valid relation
            patterns.
        """
        entity_labels = ", ".join(entity.label for entity in self.entities)
        lines = [f"Entity labels: {entity_labels}", "Relation types:"]
        if not self.relations:
            lines.append("(none)")
        for relation in self.relations:
            patterns = _format_patterns(relation.patterns) or "(none)"
            lines.append(f"- {relation.label}: {patterns}")
        return "\n".join(lines)


_GENERIC_LABELS = ["Person", "Organization", "Location", "Event", "Product"]

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
            patterns=[(src, tgt) for src in _GENERIC_LABELS for tgt in _GENERIC_LABELS],
        ),
    ],
)
