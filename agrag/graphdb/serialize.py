"""Convert graph records to driver parameters and graph node rows to models."""

import contextlib
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from agrag.common.data_models.entity import Entity
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


def node_params(
    record: NodeRecord, *, pending_job_id: UUID | None = None
) -> dict[str, Any]:
    """Build the ``$records`` entry for a node upsert.

    The Cutover Job tag travels in its own key, not inside ``properties``,
    because the upsert queries apply it with ``ON CREATE SET``: a job tags
    the nodes it creates, never a node it writes over. Left inside the
    applied property map it would be set on existing nodes too, which
    would hide a committed node from retrieval for the job's duration and
    put it in reach of the job's rollback, and rollback deletes tagged
    rows.

    Args:
        record: The node record to serialize.
        pending_job_id: The in-flight job's id, or None outside a job.

    Returns:
        A dict with ``id`` (string), ``properties`` (converted), and
        ``pending_job_id`` (the tag as a string, or None).
    """
    return {
        "id": str(record.id),
        "properties": _convert(record.properties),
        "pending_job_id": _convert(pending_job_id),
    }


def relation_params(
    record: RelationRecord, *, pending_job_id: UUID | None = None
) -> dict[str, Any]:
    """Build the ``$records`` entry for a relationship upsert.

    The Cutover Job tag travels in its own key for the same reason as in
    ``node_params``: only an edge the job creates carries it.

    Args:
        record: The relation record to serialize.
        pending_job_id: The in-flight job's id, or None outside a job.

    Returns:
        A dict with ``id``, ``start_id``, ``end_id``, ``properties``
        (converted), and ``pending_job_id`` (the tag as a string, or None).
    """
    return {
        "id": str(record.id),
        "start_id": str(record.start_id),
        "end_id": str(record.end_id),
        "properties": _convert(record.properties),
        "pending_job_id": _convert(pending_job_id),
    }


def parse_entity_node(node: object) -> Entity | None:
    """Parse one stored entity's property dict into an Entity.

    Neo4j rows carry no labels, so the label is the prefix of the node's
    ``merge_key``.

    Args:
        node: The node's properties, as a ``RETURN n`` row holds them.

    Returns:
        The entity, or ``None`` when ``node`` is not a property dict or has no
        usable ``id`` or ``merge_key``.
    """
    if not isinstance(node, Mapping):
        return None
    merge_key = node.get("merge_key")
    if node.get("id") is None or not isinstance(merge_key, str) or ":" not in merge_key:
        return None
    label, _, key_name = merge_key.partition(":")
    system_keys = {
        "name",
        "merge_key",
        "merge_count",
        "source_chunk_ids",
        "created_at",
        "embedding",
        "id",
        PENDING_JOB_ID_PROPERTY,
    }
    try:
        merge_count = int(node.get("merge_count", 1))
    except (TypeError, ValueError):
        merge_count = 1
    try:
        kwargs: dict[str, Any] = {
            "id": UUID(str(node["id"])),
            "label": label,
            "name": str(key_name if node.get("name") is None else node["name"]),
            "properties": {k: v for k, v in node.items() if k not in system_keys},
            "merge_count": merge_count,
            "source_chunk_ids": [
                UUID(str(chunk_id)) for chunk_id in node.get("source_chunk_ids") or []
            ],
        }
        if node.get("embedding") is not None:
            kwargs["embedding"] = list(node["embedding"])
        created_at = node.get("created_at")
        if isinstance(created_at, str):
            with contextlib.suppress(ValueError):
                kwargs["created_at"] = datetime.fromisoformat(created_at)
        return Entity(**kwargs)
    except (TypeError, ValueError):
        return None
