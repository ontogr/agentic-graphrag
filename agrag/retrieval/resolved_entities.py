"""Hydration helpers for materialized resolved entities."""

from typing import Any

from agrag.common.data_models.resolved_entity import ResolvedEntity


def parse_resolved_entity_node(node: object) -> ResolvedEntity | None:
    """Parse a graph-store node into a resolved entity when its shape is valid."""
    if not isinstance(node, dict):
        return None
    properties = node.get("properties", node)
    if not isinstance(properties, dict):
        return None
    values: dict[str, Any] = dict(properties)
    if "id" not in values and node.get("id") is not None:
        values["id"] = node["id"]
    try:
        return ResolvedEntity.model_validate(values)
    except (TypeError, ValueError):
        return None
