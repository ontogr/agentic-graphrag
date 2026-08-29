"""Cypher builders for constraints and native vector indexes.

Leaf module: imports nothing from ``agrag.graphdb``. See ``entities.py`` for the
identifier-validation contract shared by every Cypher builder.
"""

from typing import Any

from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import filter_clause, validate_identifier


_VECTOR_SIMILARITY: dict[Distance, str] = {
    Distance.COSINE: "cosine",
    Distance.EUCLID: "euclidean",
}


def node_id_constraint_query(label: str) -> str:
    """Build a CREATE CONSTRAINT query making ``id`` unique per node.

    Args:
        label: The node label. Must already be validated.

    Returns:
        A Cypher query creating the uniqueness constraint if absent.
    """
    safe_label = validate_identifier(label)
    return (
        f"CREATE CONSTRAINT {safe_label}_id_unique IF NOT EXISTS "
        f"FOR (n:{safe_label}) REQUIRE n.id IS UNIQUE"
    )


def plain_index_query(label: str) -> str:
    """Build a CREATE INDEX query on the node ``id`` property.

    Args:
        label: The node label. Must already be validated.

    Returns:
        A Cypher query creating the range index if absent.
    """
    safe_label = validate_identifier(label)
    return (
        f"CREATE INDEX {safe_label}_id_index IF NOT EXISTS "
        f"FOR (n:{safe_label}) ON (n.id)"
    )


def vector_index_name(label: str, vector_property: str) -> str:
    """Derive the deterministic name a vector index is created under.

    Args:
        label: The node label. Must already be validated.
        vector_property: The vector property name. Must already be validated.

    Returns:
        The index name ``ensure_vector_index`` and ``vector_search`` share.
    """
    validate_identifier(label)
    validate_identifier(vector_property)
    return f"{label}_{vector_property}_vector"


def vector_index_query(
    label: str, vector_property: str, dimensions: int, distance: Distance
) -> str:
    """Build a CREATE VECTOR INDEX query for native vector search.

    Args:
        label: The node label. Must already be validated.
        vector_property: The vector property name. Must already be validated.
        dimensions: The embedding dimension.
        distance: The distance metric, mapped to Neo4j's similarity function.

    Returns:
        A Cypher query creating the vector index if absent.

    Raises:
        ValueError: ``distance`` is not a metric Neo4j vector indexes support.
    """
    safe_label = validate_identifier(label)
    safe_property = validate_identifier(vector_property)
    try:
        similarity = _VECTOR_SIMILARITY[distance]
    except KeyError as exc:
        raise ValueError(
            f"Neo4j vector indexes do not support {distance.value!r}"
        ) from exc
    name = vector_index_name(safe_label, safe_property)
    return (
        f"CREATE VECTOR INDEX {name} IF NOT EXISTS "
        f"FOR (n:{safe_label}) ON (n.{safe_property}) "
        f"OPTIONS {{indexConfig: {{`vector.dimensions`: {dimensions}, "
        f"`vector.similarity_function`: '{similarity}'}}}}"
    )


def vector_search_query(
    index_name: str, filters: dict[str, Any] | None = None
) -> tuple[str, dict[str, Any]]:
    """Build a native vector search query and its filter parameters.

    Args:
        index_name: The vector index name from ``vector_index_name``.
        filters: An optional flat-dict filter applied with ``WHERE``.

    Returns:
        The Cypher query yielding ``node`` and ``score``, and a parameter dict
        holding only the filter parameters (the caller adds ``index``, ``k``,
        and ``vector``).
    """
    query = "CALL db.index.vector.queryNodes($index, $k, $vector) YIELD node, score "
    params: dict[str, Any] = {}
    if filters:
        where, params = filter_clause(filters)
        query += where + " "
    query += "RETURN node, score"
    return query, params
