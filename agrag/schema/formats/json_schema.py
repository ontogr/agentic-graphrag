"""Export a GraphSchema as a JSON Schema (draft 2020-12) for extraction output."""

from collections.abc import Callable
from decimal import Decimal
from typing import Any
from urllib.parse import quote

from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    PropertySpec,
    RelationType,
)
from agrag.schema.formats._iri import default_base


_DIALECT = "https://json-schema.org/draft/2020-12/schema"

_DATE_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"

_SCALARS: dict[str, dict[str, str]] = {
    "string": {"type": "string"},
    "integer": {"type": "integer"},
    "float": {"type": "number"},
    "boolean": {"type": "boolean"},
    "date": {"type": "string", "format": "date", "pattern": _DATE_PATTERN},
}


def _float_value(text: str) -> int | float:
    """Return ``text`` as an int when integral, else as a float.

    Integral text stays exact no matter its size instead of rounding to
    the nearest binary float.
    """
    number = Decimal(text)
    if number == number.to_integral_value():
        return int(number)
    return float(number)


# An enum holds text. JSON Schema compares typed values, so convert them back.
_FROM_TEXT: dict[str, Callable[[str], Any]] = {
    "string": str,
    "integer": int,
    "float": _float_value,
    "boolean": lambda text: text == "true",
    "date": str,
}


def _property_schema(spec: PropertySpec) -> dict[str, Any]:
    node: dict[str, Any] = dict(_SCALARS[spec.type])
    if spec.description:
        node["description"] = spec.description
    if spec.enum is not None:
        seen: list[Any] = []
        for value in spec.enum:
            converted = _FROM_TEXT[spec.type](value)
            if converted not in seen:
                seen.append(converted)
        node["enum"] = seen
    return node


def _entity_key(label: str) -> str:
    """Return the ``$defs`` key for an entity type."""
    return f"entity-{label}"


def _relation_key(label: str) -> str:
    """Return the ``$defs`` key for a relation type."""
    return f"relation-{label}"


def _escape_pointer(token: str) -> str:
    """Escape one ``$defs`` key for use inside a JSON Pointer ``$ref``."""
    return token.replace("~", "~0").replace("/", "~1")


def _one_of(keys: list[str]) -> dict[str, Any] | bool:
    """Reference each definition, or reject every item when there are none."""
    if not keys:
        return False
    refs = [{"$ref": f"#/$defs/{_escape_pointer(key)}"} for key in keys]
    return {"oneOf": refs}


def _entity_def(entity: EntityType) -> dict[str, Any]:
    """Return the JSON Schema definition for one entity type."""
    inner: dict[str, Any] = {
        "type": "object",
        "properties": {
            name: _property_schema(spec) for name, spec in entity.properties.items()
        },
        "additionalProperties": False,
    }
    needed = [name for name, spec in entity.properties.items() if spec.required]
    if needed:
        inner["required"] = needed
    node: dict[str, Any] = {
        "title": entity.label,
        "description": entity.description,
        "type": "object",
        "properties": {
            "label": {"const": entity.label},
            "text": {"type": "string"},
            "properties": inner,
        },
        "required": ["label", "text", "properties"],
        "additionalProperties": False,
    }
    if entity.parents:
        node["x-agrag-parents"] = list(entity.parents)
    return node


def _relation_def(
    relation: RelationType, labels: list[str], schema: GraphSchema
) -> dict[str, Any]:
    """Return the JSON Schema definition for one relation type."""
    pairs: list[dict[str, Any]] = []
    for source in labels:
        targets = [
            target for target in labels if schema.allows(relation.label, source, target)
        ]
        if targets:
            pairs.append(
                {
                    "properties": {
                        "source_label": {"const": source},
                        "target_label": {"enum": targets},
                    }
                }
            )
    node: dict[str, Any] = {
        "title": relation.label,
        "description": relation.description,
        "type": "object",
        "properties": {
            "type": {"const": relation.label},
            "source": {"type": "string"},
            "target": {"type": "string"},
        },
        "required": ["type", "source", "target", "source_label", "target_label"],
        "anyOf": pairs or [False],
        "unevaluatedProperties": False,
    }
    if relation.cardinality.max_per_source is not None:
        node["x-agrag-max-per-source"] = relation.cardinality.max_per_source
    if relation.cardinality.max_per_target is not None:
        node["x-agrag-max-per-target"] = relation.cardinality.max_per_target
    if relation.symmetric:
        node["x-agrag-symmetric"] = True
    return node


def to_json_schema(schema: GraphSchema) -> dict[str, Any]:
    """Export a schema as a JSON Schema that checks a plain extraction document.

    The result describes one document with an ``entities`` array and a
    ``relations`` array. Each entity is ``{"label", "text", "properties"}``.
    Each relation is ``{"type", "source", "target", "source_label",
    "target_label"}``. The allowed label pairs come from
    ``GraphSchema.allows``, so they cover child types and the reverse
    direction of a symmetric relation. Parents, cardinality and symmetry have
    no JSON Schema keyword, so they appear as ``x-agrag-*`` annotations that
    validators ignore.

    This is a plain interchange document for LLM structured output, not a
    dump of ``ExtractionResult`` or the BAML extraction response. Those carry
    chunk ids, character offsets, and index- or text-based endpoints that this
    shape does not model.

    Args:
        schema: The schema to export.

    Returns:
        A JSON-serializable dict. Serialize it with ``json.dumps``.
    """
    labels = [entity.label for entity in schema.entities]
    defs: dict[str, Any] = {}
    for entity in schema.entities:
        defs[_entity_key(entity.label)] = _entity_def(entity)
    for relation in schema.relations:
        defs[_relation_key(relation.label)] = _relation_def(relation, labels, schema)
    return {
        "$schema": _DIALECT,
        "$id": default_base(schema) + quote(schema.version, safe=""),
        "title": schema.name,
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "items": _one_of([_entity_key(label) for label in labels]),
            },
            "relations": {
                "type": "array",
                "items": _one_of(
                    [_relation_key(item.label) for item in schema.relations]
                ),
            },
        },
        "required": ["entities", "relations"],
        "additionalProperties": False,
        "$defs": defs,
    }
