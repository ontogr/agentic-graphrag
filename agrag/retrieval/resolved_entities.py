"""Hydration helpers for materialized resolved entities."""

from typing import Any
from uuid import UUID

from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.cypher.resolution_read import hydrate_resolved_entities_by_id_query
from agrag.graphdb.base import GraphStore


_SYSTEM_KEYS = {
    "id",
    "name",
    "label",
    "member_ids",
    "created_at",
    "vector_sync_status",
    "vector_sync_error",
    "embedding",
}


def parse_resolved_entity_node(node: object) -> ResolvedEntity | None:
    """Parse a graph-store node into a resolved entity when its shape is valid.

    Accepts both the ``{"properties": {...}}`` mock shape used in tests and a
    real Neo4j driver ``Node``, which exposes its properties through
    ``dict(node)`` rather than as a plain dict. Flat properties outside
    ``ResolvedEntity``'s own fields (for example ``description``) are routed
    into ``ResolvedEntity.properties`` instead of being dropped by pydantic.
    """
    if isinstance(node, dict) and "properties" in node:
        properties = node.get("properties")
        node_id = (
            properties.get("id") if isinstance(properties, dict) else None
        ) or node.get("id")
    else:
        try:
            properties = dict(node)  # ty: ignore[no-matching-overload]  # type: ignore[arg-type]
        except TypeError:
            return None
        node_id = None
    if not isinstance(properties, dict):
        return None
    if node_id is None:
        node_id = properties.get("id")
    if node_id is None:
        return None
    values: dict[str, Any] = {
        key: value for key, value in properties.items() if key in _SYSTEM_KEYS
    }
    values["id"] = node_id
    values["properties"] = {
        key: value for key, value in properties.items() if key not in _SYSTEM_KEYS
    }
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
        {"ids": [str(item_id) for item_id in ids], "job_id": None},
    )
    entities: dict[UUID, ResolvedEntity] = {}
    for row in rows:
        node = row.get("resolved") if isinstance(row, dict) else row
        entity = parse_resolved_entity_node(node)
        if entity is not None:
            entities[entity.id] = entity
    return entities
