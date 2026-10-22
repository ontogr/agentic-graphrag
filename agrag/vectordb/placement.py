"""Validate that a graph continues to use its original vector placement."""

from datetime import UTC, datetime

from agrag.common.data_models.vector_record import Distance
from agrag.cypher.vector_placement import (
    VECTOR_PLACEMENT_ID,
    read_placement_query,
    write_placement_query,
)
from agrag.graphdb.base import GraphStore
from agrag.vectordb.base import VectorStore
from agrag.vectordb.errors import VectorPlacementError


async def validate_placement(
    graph_store: GraphStore,
    *,
    vector_store: VectorStore | None,
    dimensions: int,
    distance: Distance,
    write: bool,
) -> None:
    """Compare placement, creating it on first open only when write is true.

    Raises:
        VectorPlacementError: Store, prefix, dimensions or distance differ.
    """
    expected = {
        "store": vector_store.name if vector_store is not None else "graph",
        "collection_prefix": (
            vector_store.collection_prefix if vector_store is not None else ""
        ),
        "dimensions": dimensions,
        "distance": distance.value,
    }
    params = {"id": str(VECTOR_PLACEMENT_ID)}
    rows = await graph_store.execute_read(read_placement_query(), params)
    if not rows and write:
        rows = await graph_store.execute_write(
            write_placement_query(),
            {**params, **expected, "created_at": datetime.now(UTC).isoformat()},
        )
    if not rows:
        return
    for key, value in expected.items():
        if rows[0][key] != value:
            raise VectorPlacementError(
                f"Vector placement {key} is {rows[0][key]!r}, requested {value!r}"
            )
