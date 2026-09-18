"""Hydration helpers for materialized resolved entities."""

from typing import Any
from uuid import UUID

from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.cypher.resolution_read import hydrate_resolved_entities_by_id_query
from agrag.graphdb.base import GraphStore


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


async def hydrate_resolved_entities(
    graph_store: GraphStore, ids: list[UUID]
) -> dict[UUID, ResolvedEntity]:
    """Hydrate resolved entities by vector-hit identifiers."""
    if not ids:
        return {}
    rows = await graph_store.execute_read(
        hydrate_resolved_entities_by_id_query(),
        {"ids": [str(item_id) for item_id in ids]},
    )
    entities: dict[UUID, ResolvedEntity] = {}
    for row in rows:
        node = row.get("resolved") if isinstance(row, dict) else row
        entity = parse_resolved_entity_node(node)
        if entity is not None:
            entities[entity.id] = entity
    return entities
