"""Convert graph records into Neo4j-driver-friendly parameters."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from agrag.common.data_models.graph_record import NodeRecord, RelationRecord


def _convert(value: Any) -> Any:
    """Recursively convert a value to a Neo4j-driver-friendly type.

    Neo4j's driver rejects ``UUID`` objects and other non-primitive types, so any
    ``UUID`` becomes its string form and nested containers are walked the same
    way.

    Args:
        value: The value to convert.

    Returns:
        The driver-safe equivalent of ``value``.
    """
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        return {k: _convert(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_convert(v) for v in value]
    return value


def node_params(record: NodeRecord) -> dict[str, Any]:
    """Build the ``$records`` entry for a node upsert.

    Args:
        record: The node record to serialize.

    Returns:
        A dict with ``id`` (string) and ``properties`` (converted).
    """
    return {"id": str(record.id), "properties": _convert(record.properties)}


def relation_params(record: RelationRecord) -> dict[str, Any]:
    """Build the ``$records`` entry for a relationship upsert.

    Args:
        record: The relation record to serialize.

    Returns:
        A dict with ``id``, ``start_id``, ``end_id``, and ``properties``.
    """
    return {
        "id": str(record.id),
        "start_id": str(record.start_id),
        "end_id": str(record.end_id),
        "properties": _convert(record.properties),
    }
