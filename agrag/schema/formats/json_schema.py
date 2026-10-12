"""Export a GraphSchema as a JSON Schema (draft 2020-12) for extraction output."""

from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from agrag.common.data_models.graph_schema import GraphSchema, PropertySpec
from agrag.schema.formats._iri import default_base


_DIALECT = "https://json-schema.org/draft/2020-12/schema"

_SCALARS: dict[str, dict[str, str]] = {
    "string": {"type": "string"},
    "integer": {"type": "integer"},
    "float": {"type": "number"},
    "boolean": {"type": "boolean"},
    "date": {"type": "string", "format": "date"},
}

# An enum holds text. JSON Schema compares typed values, so convert them back.
_FROM_TEXT: dict[str, Callable[[str], Any]] = {
    "string": str,
    "integer": int,
    "float": float,
    "boolean": lambda text: text == "true",
    "date": str,
}


def _property_schema(spec: PropertySpec) -> dict[str, Any]:
    node: dict[str, Any] = dict(_SCALARS[spec.type])
    if spec.description:
        node["description"] = spec.description
    if spec.enum is not None:
        node["enum"] = [_FROM_TEXT[spec.type](value) for value in spec.enum]
    return node


def _one_of(labels: list[str]) -> dict[str, Any] | bool:
    """Reference each definition, or reject every item when there are none."""
    if not labels:
        return False
    return {"oneOf": [{"$ref": f"#/$defs/{label}"} for label in labels]}


def to_json_schema(schema: GraphSchema) -> dict[str, Any]:
    """Export a schema as a JSON Schema that checks extraction output.

    The result describes one document with an ``entities`` array and a
    ``relations`` array. Each entity is ``{"label", "text", "properties"}``.
    Each relation is ``{"type", "source", "target", "source_label",
    "target_label"}``. The allowed label pairs come from
    ``GraphSchema.allows``, so they cover child types and the reverse
    direction of a symmetric relation. Parents, cardinality and symmetry have
    no JSON Schema keyword, so they appear as ``x-agrag-*`` annotations that
    validators ignore.

    Args:
        schema: The schema to export.

    Returns:
        A JSON-serializable dict. Serialize it with ``json.dumps``.
    """
    labels = [entity.label for entity in schema.entities]
    defs: dict[str, Any] = {}
    for entity in schema.entities:
        body: dict[str, Any] = {
            "label": {"const": entity.label},
            "text": {"type": "string"},
        }
        required = ["label", "text"]
        if entity.properties:
            inner: dict[str, Any] = {
                "type": "object",
                "properties": {
                    name: _property_schema(spec)
                    for name, spec in entity.properties.items()
                },
                "additionalProperties": False,
            }
            needed = [n for n, spec in entity.properties.items() if spec.required]
            if needed:
                inner["required"] = needed
                required.append("properties")
            body["properties"] = inner
        node: dict[str, Any] = {
            "title": entity.label,
            "description": entity.description,
            "type": "object",
            "properties": body,
            "required": required,
            "additionalProperties": False,
        }
        if entity.parents:
            node["x-agrag-parents"] = list(entity.parents)
        defs[entity.label] = node
    for relation in schema.relations:
        pairs = []
        for source in labels:
            targets = [
                target
                for target in labels
                if schema.allows(relation.label, source, target)
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
        node = {
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
        defs[relation.label] = node
    return {
        "$schema": _DIALECT,
        "$id": default_base(schema) + quote(schema.version, safe=""),
        "title": schema.name,
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "items": _one_of(labels),
            },
            "relations": {
                "type": "array",
                "items": _one_of([r.label for r in schema.relations]),
            },
        },
        "required": ["entities", "relations"],
        "additionalProperties": False,
        "$defs": defs,
    }
