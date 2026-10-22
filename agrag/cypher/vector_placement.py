"""Read and create the graph's immutable vector placement record."""

from uuid import NAMESPACE_OID, uuid5


VECTOR_PLACEMENT_LABEL = "VectorPlacement"
VECTOR_PLACEMENT_ID = uuid5(NAMESPACE_OID, VECTOR_PLACEMENT_LABEL)


def read_placement_query() -> str:
    """Return the placement record selected by its singleton id."""
    return (
        f"MATCH (node:{VECTOR_PLACEMENT_LABEL} {{id: $id}}) "
        "RETURN node.store AS store, node.collection_prefix AS collection_prefix, "
        "node.dimensions AS dimensions, node.distance AS distance"
    )


def write_placement_query() -> str:
    """Create placement once, preserving an existing concurrent creator's values."""
    return (
        f"MERGE (node:{VECTOR_PLACEMENT_LABEL} {{id: $id}}) "
        "ON CREATE SET node.store = $store, "
        "node.collection_prefix = $collection_prefix, node.dimensions = $dimensions, "
        "node.distance = $distance, node.created_at = $created_at "
        "RETURN node.store AS store, node.collection_prefix AS collection_prefix, "
        "node.dimensions AS dimensions, node.distance AS distance"
    )
