"""Shared identity resolution for merged_into chains."""

from typing import Any
from uuid import UUID

from agrag.common.data_models.entity import Entity
from agrag.cypher.entities import resolve_merged_into_query
from agrag.graphdb.base import GraphStore
from agrag.ingestion.graph import _parse_entity_node


MAX_MERGE_HOPS = 32


def _row_node_and_pointer(row: Any) -> tuple[Any, str | None]:
    """Split a resolve row into its node and its merged_into pointer."""
    if isinstance(row, dict) and "node" in row:
        pointer = row.get("merged_into")
        return row["node"], str(pointer) if pointer is not None else None

    node = row
    properties = node.get("properties") if isinstance(node, dict) else None
    pointer = None
    if isinstance(properties, dict):
        pointer = properties.get("merged_into")
    elif isinstance(node, dict):
        pointer = node.get("merged_into")
    return node, str(pointer) if pointer is not None else None


async def resolve_entity(graph_store: GraphStore, entity_id: UUID) -> Entity:
    """Return the live Entity behind an id, following merged_into.

    Every retrieval path that can produce an entity id must call
    this before wrapping the id in a SearchResult. This is the
    single place the merged_into invariant is enforced.

    A merge writes a ``merged_into`` property on the tombstone rather
    than a relationship, so the chain is walked one hop per query.

    Args:
        graph_store: Where the entity and its possible tombstone
            chain live.
        entity_id: The id a retrieval method found, which may or
            may not still be live.

    Returns:
        The live Entity, after resolving zero or more hops.

    Raises:
        ValueError: The id does not exist, its node cannot be parsed,
            the chain points at a missing node, the chain cycles, or it
            is longer than ``MAX_MERGE_HOPS``.
    """
    query = resolve_merged_into_query()
    current_id = str(entity_id)
    visited = {current_id}

    for _ in range(MAX_MERGE_HOPS + 1):
        rows = await graph_store.execute_read(query, {"id": current_id})
        if not rows:
            raise ValueError(f"Entity {current_id} not found or could not be parsed.")

        node, pointer = _row_node_and_pointer(rows[0])

        if pointer is None:
            entity = _parse_entity_node(node)
            if entity is None:
                raise ValueError(
                    f"Entity {current_id} not found or could not be parsed."
                )
            return entity

        if pointer in visited:
            raise ValueError(f"merged_into chain from {entity_id} cycles at {pointer}.")
        visited.add(pointer)
        current_id = pointer

    raise ValueError(
        f"merged_into chain from {entity_id} is longer than {MAX_MERGE_HOPS} hops."
    )
