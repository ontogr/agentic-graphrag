"""Load persisted entities by id."""

from collections.abc import Mapping, Sequence
from uuid import UUID

from opentelemetry.trace import Tracer

from agrag.common.data_models.entity import Entity
from agrag.cypher.entities import load_entities_by_id_query
from agrag.graphdb.base import GraphStore
from agrag.graphdb.serialize import parse_entity_node
from agrag.observability import get_tracer


LOAD_BATCH_SIZE = 1000


async def load_entities(
    graph_store: GraphStore, ids: Sequence[UUID], *, tracer: Tracer | None = None
) -> dict[UUID, Entity]:
    """Load the committed entities stored under the given ids.

    Reads in batches of ``LOAD_BATCH_SIZE``. Entities that an in-flight
    Cutover Job wrote are not returned.

    Args:
        graph_store: Where the entities live.
        ids: The entity ids to load. Duplicates are read once.
        tracer: Opens the loading span. None opens no recorded span.

    Returns:
        The entities by id. An id with no committed entity is absent from the
        result, so the caller decides whether that is an error.

    Raises:
        ValueError: A stored node under a requested id cannot be parsed into
            an entity.
        Exception: Whatever ``graph_store`` raised while reading.
    """
    unique_ids = list(dict.fromkeys(ids))
    if not unique_ids:
        return {}
    with get_tracer(tracer).start_as_current_span(
        "agrag.graphdb.load_entities",
        attributes={"agrag.requested_count": len(unique_ids)},
    ) as span:
        entities: dict[UUID, Entity] = {}
        for start in range(0, len(unique_ids), LOAD_BATCH_SIZE):
            batch = unique_ids[start : start + LOAD_BATCH_SIZE]
            rows = await graph_store.execute_read(
                load_entities_by_id_query(), {"ids": [str(i) for i in batch]}
            )
            for row in rows:
                node = row.get("n")
                entity = parse_entity_node(node)
                if entity is None:
                    node_id = node.get("id") if isinstance(node, Mapping) else None
                    raise ValueError(f"Stored node {node_id} is not a valid entity")
                entities[entity.id] = entity
        span.set_attribute("agrag.loaded_count", len(entities))
        return entities
