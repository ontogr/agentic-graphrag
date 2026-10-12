"""Import a GraphSchema from Pydantic model classes."""

import enum
import inspect
import re
from collections.abc import Sequence
from datetime import date
from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from agrag.schema import load_schema
from agrag.schema.formats.result import FormatWarning, ImportResult


_SCALARS: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "float",
    bool: "boolean",
    date: "date",
}
_COLLECTIONS = (list, set, frozenset, Sequence)


def _shape(annotation: Any) -> tuple[Any, bool, bool]:
    """Split an annotation into (inner type, is a collection, is optional)."""
    optional = False
    if get_origin(annotation) in (Union, UnionType):
        members = get_args(annotation)
        kept = [member for member in members if member is not type(None)]
        optional = len(kept) != len(members)
        if len(kept) != 1:
            return annotation, False, optional
        annotation = kept[0]
    if get_origin(annotation) in _COLLECTIONS:
        args = get_args(annotation)
        if not args:
            return annotation, False, optional
        return args[0], True, optional
    return annotation, False, optional


def _enum_values(inner: Any) -> list[Any] | None:
    if get_origin(inner) is Literal:
        values = list(get_args(inner))
    elif isinstance(inner, type) and issubclass(inner, enum.Enum):
        values = [member.value for member in inner]
    else:
        return None
    return values or None


def _enum_kind(values: list[Any]) -> str | None:
    """Infer one property type for enum values, or None when mixed."""
    kinds = {_SCALARS.get(type(value)) for value in values}
    if len(kinds) == 1:
        return kinds.pop()
    if kinds <= {"integer", "float"}:
        return "float"
    return None


def _enum_text(value: Any) -> str:
    """Render an enum value as the text the schema stores."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _max_length(field: FieldInfo) -> int | None:
    for item in field.metadata:
        if getattr(item, "max_length", None) is not None:
            return int(item.max_length)
    return None


def _relation_label(field_name: str) -> str:
    """Return the relation label a field name maps to."""
    return re.sub(r"[^A-Za-z0-9]+", "_", field_name).strip("_").upper()


def _parents(
    model: type[BaseModel], known: dict[type[BaseModel], str]
) -> list[type[BaseModel]]:
    """List the base classes of ``model`` that the caller also passes in."""
    return [
        base
        for base in model.__bases__
        if base in known and isinstance(base, type) and issubclass(base, BaseModel)
    ]


def _class_description(
    model: type[BaseModel], label: str, warnings: list[FormatWarning]
) -> str:
    """Return the cleaned docstring, or the label when the class has none."""
    description = inspect.cleandoc(model.__doc__) if model.__doc__ else ""
    if description:
        return description
    warnings.append(
        FormatWarning(
            "missing_description",
            label,
            "The class has no docstring; the label is the description.",
        )
    )
    return label


def _collect_relation(
    relations: dict[str, dict[str, Any]],
    *,
    label: str,
    field: FieldInfo,
    field_name: str,
    target: str,
    many: bool,
) -> None:
    """Add one pattern to the relation named after the field."""
    entry = relations.setdefault(
        _relation_label(field_name),
        {"patterns": [], "description": "", "limits": []},
    )
    entry["patterns"].append([label, target])
    entry["description"] = entry["description"] or field.description or ""
    entry["limits"].append(_max_length(field) if many else 1)


def _property_spec(
    field: FieldInfo, inner: Any, many: bool, optional: bool
) -> dict[str, Any] | None:
    """Return the canonical property dict for a field, or None when unmappable."""
    values = _enum_values(inner)
    kind: str | None = None
    if not many:
        kind = _enum_kind(values) if values else _SCALARS.get(inner)
    if kind is None:
        return None
    return {
        "type": kind,
        "required": field.is_required() and not optional,
        "enum": None if values is None else [_enum_text(value) for value in values],
        "description": field.description or "",
    }


def _entity_properties(
    model: type[BaseModel],
    label: str,
    known: dict[type[BaseModel], str],
    relations: dict[str, dict[str, Any]],
    warnings: list[FormatWarning],
) -> dict[str, Any]:
    """Read the fields of one model, filling the relation accumulator.

    A field the class redeclares replaces the inherited one, because a child
    that narrows a property does that with a new field.
    """
    inherited = {name for base in _parents(model, known) for name in base.model_fields}
    own = set(inspect.get_annotations(model))
    properties: dict[str, Any] = {}
    for field_name, field in model.model_fields.items():
        if field_name in inherited and field_name not in own:
            continue
        inner, many, optional = _shape(field.annotation)
        if inner in known:
            _collect_relation(
                relations,
                label=label,
                field=field,
                field_name=field_name,
                target=known[inner],
                many=many,
            )
            continue
        spec = _property_spec(field, inner, many, optional)
        if spec is None:
            warnings.append(
                FormatWarning(
                    "property_dropped",
                    f"{label}.{field_name}",
                    f"The type {field.annotation!r} has no schema equivalent.",
                )
            )
            continue
        properties[field_name] = spec
    return properties


def _entity_body(
    model: type[BaseModel],
    label: str,
    known: dict[type[BaseModel], str],
    relations: dict[str, dict[str, Any]],
    warnings: list[FormatWarning],
) -> dict[str, Any]:
    """Read one model class as a canonical entity dict."""
    return {
        "label": label,
        "description": _class_description(model, label, warnings),
        "parents": [known[base] for base in _parents(model, known)],
        "properties": _entity_properties(model, label, known, relations, warnings),
    }


def _relation_warnings(
    label: str,
    entry: dict[str, Any],
    limits: set[int | None],
    warnings: list[FormatWarning],
) -> None:
    """Warn when the fields of one relation disagree or none is described."""
    if len(limits) > 1:
        warnings.append(
            FormatWarning(
                "limit_loosened",
                label,
                "Fields of this relation disagree on the limit; none applies.",
            )
        )
    if not entry["description"]:
        warnings.append(
            FormatWarning(
                "missing_description",
                label,
                "The field has no description; the label is the description.",
            )
        )


def _relation_bodies(
    relations: dict[str, dict[str, Any]], warnings: list[FormatWarning]
) -> list[dict[str, Any]]:
    """Turn the collected relation fields into canonical relation dicts."""
    built = []
    for relation_label, entry in relations.items():
        limits = set(entry["limits"])
        _relation_warnings(relation_label, entry, limits, warnings)
        built.append(
            {
                "label": relation_label,
                "description": entry["description"] or relation_label,
                "patterns": entry["patterns"],
                "cardinality": {
                    "max_per_source": limits.pop() if len(limits) == 1 else None
                },
            }
        )
    return built


def from_pydantic(
    models: Sequence[type[BaseModel]], *, name: str = "custom", version: str = "1"
) -> ImportResult:
    """Read a schema from Pydantic model classes.

    Each class is an entity type: the class name is the label and the
    docstring is the description. A base class in ``models`` becomes a parent,
    and the child keeps only the fields it adds or overrides. A field typed
    as another class in ``models``, alone or in a list, is a relation named
    after the field in upper case, from the class to the field type. Any
    other field is a property. A field without a default, and not optional,
    is required. A ``Literal`` or ``Enum`` field becomes a property with
    ``enum`` values. A single-valued relation field gets a limit of one per
    source, and ``max_length`` on a list field sets the limit.
    ``Field(description=...)`` is the description of a property or relation.

    Args:
        models: The classes to read. Every class that a field refers to must
            be in this sequence.
        name: The schema name.
        version: The schema version.

    Returns:
        The schema and a warning for each field or description it dropped.

    Raises:
        SchemaLoadError: The classes do not form a valid schema, for example a
            class named ``Chunk``. The message lists every problem.
    """
    warnings: list[FormatWarning] = []
    known = {model: model.__name__ for model in models}
    relations: dict[str, dict[str, Any]] = {}
    entities = [
        _entity_body(model, label, known, relations, warnings)
        for model, label in known.items()
    ]
    data = {
        "name": name,
        "version": version,
        "entities": entities,
        "relations": _relation_bodies(relations, warnings),
    }
    return ImportResult(schema=load_schema(data), warnings=warnings)
