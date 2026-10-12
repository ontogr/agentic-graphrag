"""The GraphSchema contract: entity and relation types extraction validates against."""

import math
import re
from collections.abc import Callable
from datetime import date
from difflib import get_close_matches
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.community import COMMUNITY_LABEL
from agrag.common.data_models.cutover_job import CUTOVER_JOB_LABEL
from agrag.common.data_models.document import DOCUMENT_LABEL
from agrag.common.data_models.graph_record import PENDING_JOB_ID_PROPERTY
from agrag.common.data_models.resolved_entity import (
    RESOLVED_ENTITY_LABEL,
    RESOLVED_ENTITY_VECTOR_DELETION_LABEL,
)
from agrag.common.data_models.structure import (
    FIGURE_LABEL,
    SECTION_LABEL,
    SOURCE_LABEL,
    TABLE_LABEL,
)


# Property names an entity type may not declare. "label" and "text" are payload
# keys every mirrored entity embedding carries: the graph label a SearchFilters
# label filter matches on, and the embedding text the backends keyword-index.
# A property with one of these names would overwrite that key in the
# VectorStore payload while the GraphStore-native path keeps it as an ordinary
# node property, so the two retrieval paths would disagree. The rest are keys
# that Entity.to_node_record and the merge write set themselves, so a schema
# property with the same name would be replaced or dropped when the node is
# stored.
_RESERVED_ENTITY_PROPERTY_NAMES = frozenset(
    {
        "label",
        "text",
        "id",
        "name",
        "merge_key",
        "merge_count",
        "source_chunk_ids",
        "created_at",
        "embedding",
        PENDING_JOB_ID_PROPERTY,
    }
)

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
        RESOLVED_ENTITY_VECTOR_DELETION_LABEL,
        "Candidate",
        # These repeat NODE_IDENTITY_LABEL and MERGE_ALIAS_LABEL. They are
        # not imported because agrag.cypher.entities loads this package, so
        # the import would be circular. A unit test keeps the copies equal.
        "_Node",
        "_MergeAlias",
    }
)

# Relationship types the graph writes itself. A schema relation with one of
# these names would be written and then ignored or mistaken for a system edge
# by traversal, community detection and resolution context.
RESERVED_RELATION_TYPES = frozenset(
    {
        "HAS_PART",
        "HAS_CHILD",
        "HAS_DOCUMENT",
        "NEXT_CHUNK",
        "MENTIONED_IN",
        "MEMBER_OF",
        "MATCHES",
        "RESOLVED_AS",
        "EVIDENCED_BY",
        "SOURCE",
        "TARGET",
    }
)


def _format_patterns(patterns: list[tuple[str, str]]) -> str:
    """Render relation patterns as a comma-separated (source, target) list."""
    return ", ".join(f"({source}, {target})" for source, target in patterns)


def _plural(count: int, word: str) -> str:
    """Return ``word`` with an ``s`` unless ``count`` is one."""
    return word if count == 1 else f"{word}s"


def _format_limits(limits: "Cardinality") -> str:
    """Render declared limits without implying that stored edges satisfy them."""
    parts = [
        f"at most {limit} {_plural(limit, endpoint)} per {side}"
        for limit, endpoint, side in (
            (limits.max_per_source, "target", "source"),
            (limits.max_per_target, "source", "target"),
        )
        if limit is not None
    ]
    return "; ".join(parts)


def _find_cycle(parents: dict[str, list[str]]) -> list[str] | None:
    """Return the first cycle in a label-to-parents map, or None."""
    finished: set[str] = set()
    path: list[str] = []

    def visit(label: str) -> list[str] | None:
        if label in path:
            return [*path[path.index(label) :], label]
        if label in finished:
            return None
        path.append(label)
        for parent in parents[label]:
            cycle = visit(parent)
            if cycle is not None:
                return cycle
        path.pop()
        finished.add(label)
        return None

    for label in parents:
        cycle = visit(label)
        if cycle is not None:
            return cycle
    return None


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
        parents: Declared parent labels, nearest parent first.
        properties: Property names mapped to their ``PropertySpec``. Properties
            are not inherited from parents. ``label``, ``text`` and the keys
            the graph writes itself (``id``, ``name``, ``merge_key``,
            ``merge_count``, ``source_chunk_ids``, ``created_at``,
            ``embedding``) are rejected as names.
    """

    model_config = ConfigDict(extra="forbid")

    label: str
    description: str
    parents: list[str] = Field(default_factory=list)
    properties: dict[str, PropertySpec] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _reject_reserved_labels(self) -> "EntityType":
        reserved = sorted(RESERVED_ENTITY_LABELS & {self.label, *self.parents})
        if reserved:
            raise ValueError(
                f"Entity type '{self.label}' uses reserved label(s) {reserved}; "
                f"the graph writes its own nodes with "
                f"{sorted(RESERVED_ENTITY_LABELS)}. Rename the entity type, "
                "for example 'LegalSection' for 'Section'."
            )
        return self

    @model_validator(mode="after")
    def _reject_bad_parent_lists(self) -> "EntityType":
        if self.label in self.parents:
            raise ValueError(
                f"Entity type '{self.label}' lists itself as a parent. "
                f"Remove '{self.label}' from its parents."
            )
        repeated = sorted(
            {parent for parent in self.parents if self.parents.count(parent) > 1}
        )
        if repeated:
            raise ValueError(
                f"Entity type '{self.label}' lists parent(s) {repeated} more "
                "than once. List each parent once."
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
                f"{sorted(_RESERVED_ENTITY_PROPERTY_NAMES)} are keys that the "
                f"graph or the vector store writes itself. "
                f"Rename or remove those property names in the schema."
            )
        return self


class Cardinality(BaseModel):
    """Declared limits on distinct endpoints of one relation, across its patterns.

    Limits describe the schema but do not constrain extracted edges.

    Attributes:
        max_per_source: Maximum targets per source. None means no limit.
        max_per_target: Maximum sources per target. None means no limit.
    """

    model_config = ConfigDict(extra="forbid")

    max_per_source: int | None = Field(default=None, ge=1)
    max_per_target: int | None = Field(default=None, ge=1)


class RelationType(BaseModel):
    """One kind of relation a schema recognizes.

    Attributes:
        label: The relation label used in the extraction prompt and the graph.
            It must not be a relationship type the graph writes itself.
        description: Guidance fed to the extractor prompt or schema builder.
        patterns: Valid (source_label, target_label) pairs. A pattern also covers
            children of its endpoint types.
        cardinality: Optional edge limits on each side.
        symmetric: Whether each allowed edge is allowed in reverse too.
    """

    model_config = ConfigDict(extra="forbid")

    label: str
    description: str
    patterns: list[tuple[str, str]]
    cardinality: Cardinality = Field(default_factory=Cardinality)
    symmetric: bool = False

    @model_validator(mode="after")
    def _reject_reserved_labels(self) -> "RelationType":
        if self.label in RESERVED_RELATION_TYPES:
            raise ValueError(
                f"Relation type '{self.label}' uses a reserved relationship "
                f"type; the graph writes its own edges with "
                f"{sorted(RESERVED_RELATION_TYPES)}. Rename the relation type, "
                "for example 'BELONGS_TO' for 'MEMBER_OF'."
            )
        return self

    @model_validator(mode="after")
    def _check_symmetric_limits(self) -> "RelationType":
        limits = self.cardinality
        if self.symmetric and limits.max_per_source != limits.max_per_target:
            raise ValueError(
                f"Relation '{self.label}' is symmetric, so max_per_source and "
                f"max_per_target must be equal; got {limits.max_per_source} and "
                f"{limits.max_per_target}. Set both to the same value."
            )
        return self


def _validate_hierarchy(entities: list[EntityType]) -> None:
    """Raise ValueError when entity labels repeat or parents are invalid."""
    labels = [entity.label for entity in entities]
    repeated = sorted({label for label in labels if labels.count(label) > 1})
    if repeated:
        raise ValueError(
            f"Entity type label(s) {repeated} are declared more than once. "
            "Merge the declarations or rename one."
        )
    declared = set(labels)
    for entity in entities:
        for parent in entity.parents:
            if parent not in declared:
                close = get_close_matches(parent, sorted(declared), n=1)
                hint = f" Did you mean '{close[0]}'?" if close else ""
                raise ValueError(
                    f"Entity type '{entity.label}' names unknown parent "
                    f"'{parent}'. Declare '{parent}' as an entity type or "
                    f"fix the spelling.{hint}"
                )
    cycle = _find_cycle({entity.label: entity.parents for entity in entities})
    if cycle is not None:
        raise ValueError(
            f"Entity type parents form a cycle: {' -> '.join(cycle)}. "
            "Remove one parent link in the cycle."
        )


class GraphSchema(BaseModel):
    """A versioned contract of entity and relation types.

    Every extraction call is validated against a GraphSchema. There is no
    schema-free extraction path. Round-trip with
    ``model_dump(mode="json")`` and ``model_validate()``. A schema declaring
    an entity property name that the vector payload reserves fails that
    validation. See ``EntityType.properties``.

    Construct a new schema to change its types. Ancestor access revalidates the
    hierarchy so direct parent edits cannot cause an invalid traversal.

    Attributes:
        name: A short, unique name for this schema.
        version: The schema version. Bump when types or patterns change.
        entities: The entity types this schema recognizes.
        relations: The relation types this schema recognizes.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    entities: list[EntityType]
    relations: list[RelationType]

    @model_validator(mode="after")
    def _validate_entity_types(self) -> "GraphSchema":
        _validate_hierarchy(self.entities)
        return self

    @model_validator(mode="after")
    def _validate_patterns(self) -> "GraphSchema":
        """Reject duplicate relation labels and invalid relation patterns."""
        relation_labels = [relation.label for relation in self.relations]
        repeated = sorted(
            {label for label in relation_labels if relation_labels.count(label) > 1}
        )
        if repeated:
            raise ValueError(
                f"Relation type label(s) {repeated} are declared more than once. "
                "Merge the declarations into one relation type."
            )
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
                if rel.symmetric and not self._related(source, target):
                    raise ValueError(
                        f"Relation '{rel.label}' is symmetric, so both ends of "
                        f"pattern ({source}, {target}) must be the same type, or "
                        "one must be an ancestor of the other. Change the "
                        "pattern or set symmetric to false."
                    )
        return self

    def ancestors(self, label: str) -> list[str]:
        """Return an entity type's ancestors in nearest-first breadth-first order.

        Parents retain their listed order. Shared ancestors appear only once.

        Args:
            label: A declared entity label.

        Raises:
            ValueError: If the label is not declared or the hierarchy is invalid.
        """
        _validate_hierarchy(self.entities)
        by_label = {entity.label: entity for entity in self.entities}
        if label not in by_label:
            raise ValueError(
                f"Unknown entity type '{label}'. Declared entity types: "
                f"{sorted(by_label)}."
            )
        found: list[str] = []
        frontier = [label]
        while frontier:
            next_frontier: list[str] = []
            for current in frontier:
                for parent in by_label[current].parents:
                    if parent not in found:
                        found.append(parent)
                        next_frontier.append(parent)
            frontier = next_frontier
        return found

    def node_labels(self, label: str) -> list[str]:
        """Return a node's leaf label followed by its ancestors.

        Args:
            label: A declared entity label.

        Raises:
            ValueError: If the label is not declared or the hierarchy is invalid.
        """
        return [label, *self.ancestors(label)]

    def allows(self, relation: str, source_label: str, target_label: str) -> bool:
        """Return whether a pair of entity types is allowed for a relation.

        Patterns cover descendants, and symmetric relations accept reversal.
        Unknown entity or relation labels return False.
        Invalid parent edits raise ValueError rather than traversing bad data.

        Args:
            relation: The relation label.
            source_label: The source entity's leaf label.
            target_label: The target entity's leaf label.
        """
        rel = next((item for item in self.relations if item.label == relation), None)
        declared = {entity.label for entity in self.entities}
        if rel is None or source_label not in declared or target_label not in declared:
            return False
        source_labels = set(self.node_labels(source_label))
        target_labels = set(self.node_labels(target_label))
        if any(s in source_labels and t in target_labels for s, t in rel.patterns):
            return True
        return rel.symmetric and any(
            s in target_labels and t in source_labels for s, t in rel.patterns
        )

    def resolve(self) -> str:
        """Render entity details and relation patterns expanded over child types.

        The final line counts entity and relation labels.
        """
        lines = [f"Schema {self.name} (version {self.version})", "Entity types:"]
        for entity in self.entities:
            lines.append(f"- {entity.label}: {entity.description}")
            if entity.parents:
                lines.append(f"  parents: {', '.join(entity.parents)}")
        lines.append("Relation types:")
        for relation in self.relations:
            lines.append(f"- {relation.label}: {relation.description}")
            pairs = [
                f"({source.label}, {target.label})"
                for source in self.entities
                for target in self.entities
                if self.allows(relation.label, source.label, target.label)
            ]
            lines.append(f"  valid patterns: {', '.join(pairs) or '(none)'}")
        lines.append(f"Total labels: {len(self.entities) + len(self.relations)}")
        return "\n".join(lines)

    def _related(self, first: str, second: str) -> bool:
        """Return whether declared types are equal or related by ancestry."""
        return (
            first == second
            or first in self.ancestors(second)
            or second in self.ancestors(first)
        )

    def to_prompt_description(self) -> str:
        """Serialize this schema in full for an LLM prompt.

        Entity labels, parents and declared properties are followed by each
        relation's valid patterns, symmetry and cardinality. Use
        ``to_compact_summary`` instead when prompt space is tight.

        Returns:
            A plain-text schema description, one fact per line.
        """
        lines = [f"Schema {self.name} (version {self.version})", "Entity types:"]
        for entity in self.entities:
            lines.append(f"- {entity.label}: {entity.description}")
            if entity.parents:
                lines.append(f"  parents: {', '.join(entity.parents)}")
            if entity.properties:
                lines.append("  properties:")
                for name, spec in entity.properties.items():
                    line = f"    - {spec.describe(name)}"
                    if spec.description:
                        line += f": {spec.description}"
                    lines.append(line)
        lines.append("Relation types:")
        if not self.relations:
            lines.append("(none)")
        for relation in self.relations:
            lines.append(f"- {relation.label}: {relation.description}")
            patterns = _format_patterns(relation.patterns) or "(none)"
            lines.append(f"  valid patterns: {patterns}")
            if relation.symmetric:
                lines.append("  symmetric: yes")
            limits = _format_limits(relation.cardinality)
            if limits:
                lines.append(f"  declared limits (not enforced): {limits}")
        if any(entity.parents for entity in self.entities):
            lines.append(
                "Note: a pattern that names a type allows every child of that type."
            )
            lines.append(
                "Stored nodes carry only their leaf label. Queries for a parent "
                "type must also match all descendant labels."
            )
        return "\n".join(lines)

    def to_compact_summary(self) -> str:
        """Serialize entity labels, parents and relation patterns for a prompt.

        Descriptions, properties and cardinality limits are omitted, so this is
        the shape to inject where prompt space is tight.
        ``to_prompt_description`` carries the same labels with their
        full detail.

        Returns:
            A plain-text summary of entity labels and valid relation
            patterns.
        """
        entity_labels = ", ".join(
            f"{entity.label} (parents: {', '.join(entity.parents)})"
            if entity.parents
            else entity.label
            for entity in self.entities
        )
        lines = [f"Entity labels: {entity_labels}", "Relation types:"]
        if not self.relations:
            lines.append("(none)")
        for relation in self.relations:
            patterns = _format_patterns(relation.patterns) or "(none)"
            mark = " [symmetric]" if relation.symmetric else ""
            lines.append(f"- {relation.label}: {patterns}{mark}")
        if any(entity.parents for entity in self.entities):
            lines.append(
                "Patterns naming a type also cover its descendants. Stored nodes "
                "carry only their leaf label; parent queries must include descendants."
            )
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
