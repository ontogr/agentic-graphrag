"""Convert graph records into Neo4j-driver-friendly parameters."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from agrag.common.data_models.graph_record import (
    PENDING_JOB_ID_PROPERTY,
    NodeRecord,
    RelationRecord,
)


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

    The Cutover Job tag is split out of ``properties`` into its own key
    because the upsert queries apply it with ``ON CREATE SET``: a job tags
    the nodes it creates, never a node it writes over. Left inside the
    applied property map it would be set on existing nodes too, which
    would hide a committed node from retrieval for the job's duration and
    put it in reach of the job's rollback — and rollback deletes tagged
    rows.

    Args:
        record: The node record to serialize.

    Returns:
        A dict with ``id`` (string), ``properties`` (converted, without
        the pending tag), and ``pending_job_id`` (the tag, or None).
    """
    properties = dict(record.properties)
    pending_job_id = properties.pop(PENDING_JOB_ID_PROPERTY, None)
    return {
        "id": str(record.id),
        "properties": _convert(properties),
        "pending_job_id": _convert(pending_job_id),
    }


def relation_params(record: RelationRecord) -> dict[str, Any]:
    """Build the ``$records`` entry for a relationship upsert.

    The Cutover Job tag is split out of ``properties`` for the same reason
    as in :func:`node_params`: only an edge the job creates carries it.

    Args:
        record: The relation record to serialize.

    Returns:
        A dict with ``id``, ``start_id``, ``end_id``, ``properties``
        (converted, without the pending tag), and ``pending_job_id`` (the
        tag, or None).
    """
    properties = dict(record.properties)
    pending_job_id = properties.pop(PENDING_JOB_ID_PROPERTY, None)
    return {
        "id": str(record.id),
        "start_id": str(record.start_id),
        "end_id": str(record.end_id),
        "properties": _convert(properties),
        "pending_job_id": _convert(pending_job_id),
    }
