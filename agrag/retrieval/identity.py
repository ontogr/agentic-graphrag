"""Shared identity resolution for merged_into chains."""

from uuid import UUID

from agrag.common.data_models.entity import Entity
from agrag.cypher.entities import (
    NODE_IDENTITY_LABEL,
    resolve_merged_into_query,
)
from agrag.graphdb.base import GraphStore
from agrag.ingestion.graph import _parse_entity_node


async def resolve_entity(graph_store: GraphStore, entity_id: UUID) -> Entity:
    """Return the live Entity behind an id, following merged_into.

    Every retrieval path that can produce an entity id must call
    this before wrapping the id in a SearchResult. This is the
    single place the merged_into invariant is enforced.

    Args:
        graph_store: Where the entity and its possible tombstone
            chain live.
        entity_id: The id a retrieval method found, which may or
            may not still be live.

    Returns:
        The live Entity, after resolving zero or more hops.
    """
    rows = await graph_store.execute_read(
        resolve_merged_into_query(max_hops=32),
        {"id": str(entity_id)},
    )
    if rows:
        live_row = rows[0]
        live_node = (
            live_row.get("live")
            if isinstance(live_row, dict) and "live" in live_row
            else live_row
        )
        entity = _parse_entity_node(live_node)
        if entity is not None:
            return entity

    # Fallback: direct fetch (entity was live, zero hops)
    rows = await graph_store.execute_read(
        f"MATCH (n:{NODE_IDENTITY_LABEL} {{id: $id}}) "
        f"WHERE n.merged_into IS NULL "
        f"RETURN n",
        {"id": str(entity_id)},
    )
    if rows:
        node = (
            rows[0].get("n")
            if isinstance(rows[0], dict) and "n" in rows[0]
            else rows[0]
        )
        entity = _parse_entity_node(node)
        if entity is not None:
            return entity

    raise ValueError(f"Entity {entity_id} not found or could not be parsed.")
