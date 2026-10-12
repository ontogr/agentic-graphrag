"""The GraphSchema contract: entity and relation types extraction validates against."""

import math
import re
from collections.abc import Callable
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.community import COMMUNITY_LABEL
from agrag.common.data_models.cutover_job import CUTOVER_JOB_LABEL
from agrag.common.data_models.document import DOCUMENT_LABEL
from agrag.common.data_models.resolved_entity import RESOLVED_ENTITY_LABEL
from agrag.common.data_models.structure import (
    FIGURE_LABEL,
    SECTION_LABEL,
    SOURCE_LABEL,
    TABLE_LABEL,
)


# Payload keys every mirrored entity embedding carries: the graph label a
# SearchFilters label filter matches on, and the embedding text the backends
# keyword-index. An entity property with one of these names would overwrite
# that key in the VectorStore payload while the GraphStore-native path keeps
# it as an ordinary node property, so the two retrieval paths would disagree.
_RESERVED_ENTITY_PROPERTY_NAMES = frozenset({"label", "text"})

RESERVED_ENTITY_LABELS = frozenset(
    {
        DOCUMENT_LABEL,
        CHUNK_LABEL,
        SECTION_LABEL,
        TABLE_LABEL,
        FIGURE_LABEL,
        SOURCE_LABEL,
        COMMUNITY_LABEL,
        RESOLVED_ENTITY_LABEL,
        CUTOVER_JOB_LABEL,
        # These repeat NODE_IDENTITY_LABEL and MERGE_ALIAS_LABEL. They are
        # not imported because agrag.cypher.entities loads this package, so
        # the import would be circular. A unit test keeps the copies equal.
        "_Node",
        "_MergeAlias",
    }
)


def _format_patterns(patterns: list[tuple[str, str]]) -> str:
    """Render relation patterns as a comma-separated (source, target) list."""
    return ", ".join(f"({source}, {target})" for source, target in patterns)


PropertyType = Literal["string", "integer", "float", "boolean", "date"]
"""The value types an entity property can declare."""

_INTEGER_VALUE = re.compile(r"-?[0-9]+")
_FLOAT_VALUE = re.compile(r"-?[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?")
_DATE_VALUE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _is_valid_float(value: str) -> bool:
    """Return whether ``value`` is a finite decimal or exponent number."""
    return _FLOAT_VALUE.fullmatch(value) is not None and math.isfinite(float(value))


def _is_valid_date(value: str) -> bool:
    """Return whether ``value`` is a real calendar date as ``YYYY-MM-DD``."""
    if _DATE_VALUE.fullmatch(value) is None:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


_VALUE_CHECKS: dict[str, Callable[[str], bool]] = {
    "string": lambda value: bool(value.strip()),
    "integer": lambda value: _INTEGER_VALUE.fullmatch(value) is not None,
    "float": _is_valid_float,
    "boolean": lambda value: value in {"true", "false"},
    "date": _is_valid_date,
}

_VALUE_HINTS = {
    "string": "A string value must not be blank.",
    "integer": "An integer value looks like 12 or -3.",
    "float": "A float value looks like 1.5 or -2e3.",
    "boolean": "A boolean value is 'true' or 'false'.",
    "date": "A date value looks like 2024-01-31.",
}


class PropertySpec(BaseModel):
    """The declaration of one property on an entity type.

    A spec describes the property but does not validate extracted values.

    Attributes:
        type: The value type: ``string``, ``integer``, ``float``, ``boolean`` or
            ``date``.
        required: Whether an entity of this type should carry the property.
        enum: Allowed values as text, or None for no restriction. Each value
            must be a valid text form of ``type``.
        description: Guidance for the extractor. Empty when there is none.
    """

    model_config = ConfigDict(extra="forbid")

    type: PropertyType
    required: bool = False
    enum: list[str] | None = None
    description: str = ""

    @model_validator(mode="after")
    def _check_enum_values(self) -> "PropertySpec":
        if self.enum is None:
            return self
        if not self.enum:
            raise ValueError(
                "enum is empty; list at least one allowed value, or remove enum."
            )
        repeated = sorted({value for value in self.enum if self.enum.count(value) > 1})
        if repeated:
            raise ValueError(
                f"enum lists {repeated} more than once. Remove the repeated values."
            )
        invalid = [value for value in self.enum if not _VALUE_CHECKS[self.type](value)]
        if invalid:
            raise ValueError(
                f"enum value(s) {invalid} are not valid for type '{self.type}'. "
                f"{_VALUE_HINTS[self.type]}"
            )
        return self

    def describe(self, name: str) -> str:
        """Render this property as one prompt phrase."""
        traits: list[str] = [self.type]
        if self.required:
            traits.append("required")
        if self.enum is not None:
            traits.append(f"one of: {', '.join(self.enum)}")
        return f"{name} ({', '.join(traits)})"


class EntityType(BaseModel):
    """One kind of entity a schema recognizes.

    Attributes:
        label: The node label used in the extraction prompt and the graph.
        description: Guidance fed to the extractor prompt or schema builder.
        properties: Property names mapped to their ``PropertySpec``. ``label``
            and ``text`` are rejected as names, because retrieval filtering and
            keyword search use both as vector payload keys.
        subtypes: Labels that narrow this type. Empty when this type has no subtypes.
    """

    label: str
    description: str
    properties: dict[str, PropertySpec] = Field(default_factory=dict)
    subtypes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _reject_reserved_labels(self) -> "EntityType":
        reserved = sorted(RESERVED_ENTITY_LABELS & {self.label, *self.subtypes})
        if reserved:
            raise ValueError(
                f"Entity type '{self.label}' uses reserved label(s) {reserved}; "
                f"the graph writes its own nodes with "
                f"{sorted(RESERVED_ENTITY_LABELS)}. Rename the entity type, "
                "for example 'LegalSection' for 'Section'."
            )
        return self

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

    Every extraction call is validated against a GraphSchema. There is no
    schema-free extraction path. Round-trip with
    ``model_dump(mode="json")`` and ``model_validate()``. A schema declaring
    an entity property name that the vector payload reserves fails that
    validation, so a payload written before the check existed must be migrated
    before it loads again. See ``EntityType.properties``.

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
        ``to_compact_summary`` instead when prompt space is tight.

        Returns:
            A plain-text schema description, one fact per line.
        """
        lines = [f"Schema {self.name} (version {self.version})", "Entity types:"]
        for entity in self.entities:
            lines.append(f"- {entity.label}: {entity.description}")
            if entity.properties:
                lines.append("  properties:")
                for name, spec in entity.properties.items():
                    line = f"    - {spec.describe(name)}"
                    if spec.description:
                        line += f": {spec.description}"
                    lines.append(line)
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
        ``to_prompt_description`` carries the same labels with their
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
"""A ready-made schema for open-domain text.

It declares five entity types (``Person``, ``Organization``, ``Location``,
``Event``, and ``Product``) and one relation, ``RELATED_TO``, allowed between any
two of them. Use it to try agrag without writing a schema.
"""
