"""The canonical dict form of a GraphSchema."""

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from agrag.common.data_models.graph_schema import GraphSchema
from agrag.schema.errors import Issues


def dump_schema(schema: GraphSchema) -> dict[str, Any]:
    """Return the canonical dict form of a schema.

    The canonical form holds every field, with no shorthand. Entity and
    relation order is kept, and each relation pattern is a ``[source, target]``
    list. ``load_schema(dump_schema(schema)) == schema`` for every valid
    schema, and the dump is plain JSON data.

    Args:
        schema: The schema to dump.

    Returns:
        A new dict that the caller may change freely.
    """
    return schema.model_dump(mode="json")


def _locate(loc: tuple[int | str, ...], origins: Mapping[str, list[str]]) -> str:
    """Turn a model error location into a path in the source."""
    if not loc:
        return "schema"
    head, rest = loc[0], loc[1:]
    if isinstance(head, str) and head in origins and rest and isinstance(rest[0], int):
        base, rest = origins[head][rest[0]], rest[1:]
    else:
        base = str(head)
    path = base
    for part in rest:
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path


def build_schema(
    data: dict[str, Any], origins: Mapping[str, list[str]], issues: Issues
) -> GraphSchema | None:
    """Validate a canonical dict and map model errors back to source paths.

    Args:
        data: A canonical dict.
        origins: For ``entities`` and ``relations``, the source path of each
            item in ``data``, in the same order.
        issues: Receives one issue per model error.

    Returns:
        The schema, or ``None`` when the model rejects ``data``.
    """
    try:
        return GraphSchema.model_validate(data)
    except ValidationError as exc:
        for error in exc.errors():
            message = error["msg"].removeprefix("Value error, ")
            issues.add(_locate(error["loc"], origins), message)
        return None
