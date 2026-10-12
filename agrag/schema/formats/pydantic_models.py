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
        return get_args(annotation)[0], True, optional
    return annotation, False, optional


def _enum_values(inner: Any) -> list[Any] | None:
    if get_origin(inner) is Literal:
        values = list(get_args(inner))
    elif isinstance(inner, type) and issubclass(inner, enum.Enum):
        values = [member.value for member in inner]
    else:
        return None
    return values or None


def _max_length(field: FieldInfo) -> int | None:
    for item in field.metadata:
        if getattr(item, "max_length", None) is not None:
            return int(item.max_length)
    return None


def _relation_label(field_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", field_name).strip("_").upper()


def from_pydantic(
    models: Sequence[type[BaseModel]], *, name: str = "custom", version: str = "1"
) -> ImportResult:
    """Read a schema from Pydantic model classes.

    Each class is an entity type: the class name is the label and the
    docstring is the description. A base class in ``models`` becomes a parent,
    and the child keeps only the fields it adds. A field typed as another class
    in ``models``, alone or in a list, is a relation named after the field in
    upper case, from the class to the field type. Any other field is a
    property. A field without a default, and not optional, is required. A
    ``Literal`` or ``Enum`` field becomes a property with ``enum`` values. A
    single-valued relation field gets a limit of one per source, and
    ``max_length`` on a list field sets the limit. ``Field(description=...)``
    is the description of a property or relation.

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
    entities: list[dict[str, Any]] = []
    for model, label in known.items():
        bases: list[type[BaseModel]] = [
            base
            for base in model.__bases__
            if base in known and isinstance(base, type) and issubclass(base, BaseModel)
        ]
        inherited = {field for base in bases for field in base.model_fields}
        description = inspect.cleandoc(model.__doc__) if model.__doc__ else ""
        if not description:
            warnings.append(
                FormatWarning(
                    "missing_description",
                    label,
                    "The class has no docstring; the label is the description.",
                )
            )
        properties: dict[str, Any] = {}
        for field_name, field in model.model_fields.items():
            if field_name in inherited:
                continue
            inner, many, optional = _shape(field.annotation)
            if inner in known:
                entry = relations.setdefault(
                    _relation_label(field_name),
                    {"patterns": [], "description": "", "limits": []},
                )
                entry["patterns"].append([label, known[inner]])
                entry["description"] = entry["description"] or field.description or ""
                entry["limits"].append(_max_length(field) if many else 1)
                continue
            values = _enum_values(inner)
            kind = None if many else _SCALARS.get(type(values[0]) if values else inner)
            if kind is None:
                warnings.append(
                    FormatWarning(
                        "property_dropped",
                        f"{label}.{field_name}",
                        f"The type {field.annotation!r} has no schema equivalent.",
                    )
                )
                continue
            properties[field_name] = {
                "type": kind,
                "required": field.is_required() and not optional,
                "enum": None if values is None else [str(value) for value in values],
                "description": field.description or "",
            }
        entities.append(
            {
                "label": label,
                "description": description or label,
                "parents": [known[base] for base in bases],
                "properties": properties,
            }
        )
    built = []
    for relation_label, entry in relations.items():
        limits = set(entry["limits"])
        if len(limits) > 1:
            warnings.append(
                FormatWarning(
                    "limit_loosened",
                    relation_label,
                    "Fields of this relation disagree on the limit; none applies.",
                )
            )
        if not entry["description"]:
            warnings.append(
                FormatWarning(
                    "missing_description",
                    relation_label,
                    "The field has no description; the label is the description.",
                )
            )
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
    data = {"name": name, "version": version, "entities": entities, "relations": built}
    return ImportResult(schema=load_schema(data), warnings=warnings)
