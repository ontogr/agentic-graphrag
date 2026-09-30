"""Convert graph records to driver parameters and graph node rows to models."""

import contextlib
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import (
    PENDING_JOB_ID_PROPERTY,
    NodeRecord,
    RelationRecord,
)
from agrag.cypher.entities import NODE_IDENTITY_LABEL


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


def parse_entity_node(node: object) -> Entity | None:  # noqa: PLR0912,PLR0915
    """Parse a GraphStore node row into an Entity.

    Handles both neo4j Node objects and plain dict mocks used in unit tests.
    """
    try:
        props: dict = {}
        labels: list[str] = []
        node_id: object = None

        if isinstance(node, dict) and "labels" in node and "properties" in node:
            # Mock form: {"id": "...", "labels": [...], "properties": {...}}
            labels = list(node.get("labels") or [])
            props = dict(node.get("properties") or {})
            node_id = node.get("id") or props.get("id")
        elif isinstance(node, dict) and "id" in node:
            # Flat mock where properties are top-level alongside id/labels
            # e.g. {"n": {"id": "...", "name": "...", "merge_key": "..."}}
            # But here node is that inner dict.
            props = dict(node)
            # id may be in props
            node_id = props.get("id")
            # labels might be in props or separate
            maybe_labels = props.pop("labels", None)
            if isinstance(maybe_labels, list):
                labels = maybe_labels
            # Try to get labels from node dict if present alongside
            if not labels and "labels" in props:
                labels = props.pop("labels")  # type: ignore[assignment]
        else:
            # Attempt neo4j Node: dict(node) gives properties, node.labels gives labels
            try:
                props = dict(node)  # ty: ignore[no-matching-overload]  # type: ignore[arg-type]
            except Exception:
                props = {}
            try:
                maybe_labels = getattr(node, "labels", None)
                if maybe_labels is not None:
                    labels = list(maybe_labels)  # type: ignore[arg-type]
            except Exception:
                labels = []
            # Try id from props or node["id"]
            try:
                node_id = props.get("id")  # type: ignore[union-attr]
            except Exception:
                node_id = None
            if node_id is None:
                with contextlib.suppress(Exception):
                    node_id = node["id"]  # type: ignore[index]  # ty: ignore[not-subscriptable]
            # Node may also be wrapped as {"n": Node}
            if isinstance(node, dict) and "n" in node:
                return parse_entity_node(node["n"])

        if node_id is None:
            # Fallback: id inside props
            node_id = props.get("id")

        # Determine label
        label: str | None = None
        if labels:
            for lbl in labels:
                if lbl not in (NODE_IDENTITY_LABEL, CHUNK_LABEL):
                    label = str(lbl)
                    break
            if label is None:
                # All labels were system labels, take first
                label = str(labels[0]) if labels else None
        if label is None:
            # Fallback from merge_key
            mk = props.get("merge_key") or ""
            if isinstance(mk, str) and ":" in mk:
                label = mk.split(":", 1)[0]

        if label is None or node_id is None:
            return None

        # System keys not part of domain properties
        system_keys = {
            "name",
            "merge_key",
            "merged_from",
            "merge_count",
            "source_chunk_ids",
            "created_at",
            "embedding",
            "id",
            PENDING_JOB_ID_PROPERTY,
        }
        entity_props = {k: v for k, v in props.items() if k not in system_keys}

        merged_from_raw = props.get("merged_from") or []
        merged_from = [UUID(str(x)) for x in merged_from_raw if x]

        try:
            merge_count = int(props.get("merge_count", 1))
        except Exception:
            merge_count = 1

        scids_raw = props.get("source_chunk_ids") or []
        scids = [UUID(str(x)) for x in scids_raw if x]

        embedding = props.get("embedding")

        created_at_raw = props.get("created_at")
        created_at = None
        if isinstance(created_at_raw, str):
            try:
                created_at = datetime.fromisoformat(created_at_raw)
            except Exception:
                created_at = None

        name_val = props.get("name")
        if name_val is None:
            mk = props.get("merge_key", "")
            if isinstance(mk, str) and ":" in mk:
                name_val = mk.split(":", 1)[1]
            else:
                name_val = mk or ""

        kwargs: dict = {
            "id": UUID(str(node_id)),
            "label": label,
            "name": str(name_val),
            "properties": entity_props,
            "merged_from": merged_from,
            "merge_count": merge_count,
            "source_chunk_ids": scids,
        }
        if embedding is not None:
            kwargs["embedding"] = list(embedding)  # type: ignore[arg-type]
        if created_at is not None:
            kwargs["created_at"] = created_at
        return Entity(**kwargs)
    except Exception:
        return None
