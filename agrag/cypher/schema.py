"""Cypher builders for constraints and native vector indexes.

Leaf module: imports nothing from ``agrag.graphdb``. See ``entities.py`` for the
identifier-validation contract shared by every Cypher builder.
"""

from typing import Any

from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import MERGE_ALIAS_LABEL, filter_clause, validate_identifier


_VECTOR_SIMILARITY: dict[Distance, str] = {
    Distance.COSINE: "cosine",
    Distance.EUCLID: "euclidean",
}


def node_id_constraint_query(label: str) -> str:
    """Build a CREATE CONSTRAINT query making ``id`` unique per node.

    Neo4j constraint names share one flat, global namespace regardless of
    whether they apply to a node label or a relationship type, so this name
    is kind-prefixed and length-prefixed the same way ``vector_index_name``
    is: label ``"X_rel"`` and relationship type ``"X"`` would otherwise both
    produce ``X_rel_id_unique``, and ``IF NOT EXISTS`` would then silently
    leave the second one never created.

    Args:
        label: The node label. Must already be validated.

    Returns:
        A Cypher query creating the uniqueness constraint if absent.
    """
    safe_label = validate_identifier(label)
    name = f"node_{len(safe_label)}_{safe_label}_id_unique"
    return (
        f"CREATE CONSTRAINT {name} IF NOT EXISTS "
        f"FOR (n:{safe_label}) REQUIRE n.id IS UNIQUE"
    )


def relation_id_constraint_query(rel_type: str) -> str:
    """Build a CREATE CONSTRAINT query making ``id`` unique per relationship type.

    This backs the stale-relationship lookup in ``upsert_relation_query`` with
    an index and guarantees at most one relationship of ``rel_type`` carries a
    given id. See ``node_id_constraint_query`` for why the name is
    kind-prefixed and length-prefixed rather than a plain concatenation.

    Args:
        rel_type: The relationship type. Must already be validated.

    Returns:
        A Cypher query creating the uniqueness constraint if absent.
    """
    safe_type = validate_identifier(rel_type)
    name = f"rel_{len(safe_type)}_{safe_type}_id_unique"
    return (
        f"CREATE CONSTRAINT {name} IF NOT EXISTS "
        f"FOR ()-[r:{safe_type}]-() REQUIRE r.id IS UNIQUE"
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


def merge_key_constraint_query(label: str) -> str:
    """Build a CREATE CONSTRAINT query making ``merge_key`` unique per label.

    Backs the concurrent-ingestion safety tier: two concurrent ``add()`` calls
    for the same ``(label, normalized name)`` cannot both create a canonical
    node; the second fails the constraint and is resolved to the canonical via
    the merge path. Tombstoned nodes clear their ``merge_key`` when marked
    ``merged_into``, so the constraint permits one live survivor per key plus
    any number of tombstones.

    Args:
        label: The node label. Must already be validated.

    Returns:
        A Cypher query creating the uniqueness constraint if absent.
    """
    safe_label = validate_identifier(label)
    name = f"node_{len(safe_label)}_{safe_label}_merge_key_unique"
    return (
        f"CREATE CONSTRAINT {name} IF NOT EXISTS "
        f"FOR (n:{safe_label}) REQUIRE n.merge_key IS UNIQUE"
    )


def merge_alias_constraint_query() -> str:
    """Build a CREATE CONSTRAINT query making the merge-key alias table unique.

    One global constraint, not per label: ``MERGE_ALIAS_LABEL`` is shared
    across every entity type, and ``merge_key`` already embeds the label
    (see ``Entity.merge_key``), so a single uniqueness constraint on it is
    sufficient.

    Returns:
        A Cypher query creating the uniqueness constraint if absent.
    """
    return (
        f"CREATE CONSTRAINT {MERGE_ALIAS_LABEL.lower()}_merge_key_unique IF NOT EXISTS "
        f"FOR (a:{MERGE_ALIAS_LABEL}) REQUIRE a.merge_key IS UNIQUE"
    )


def vector_index_name(label: str, vector_property: str) -> str:
    """Derive the deterministic name a vector index is created under.

    Each component is length-prefixed so the encoding is unambiguous: a plain
    join like ``f"{label}_{vector_property}_vector"`` would let a label and
    property containing underscores collide, for example ``("A_B", "C")`` and
    ``("A", "B_C")`` both joining to ``"A_B_C_vector"``. A collision would
    make ``ensure_vector_index`` reuse one index for two different label and
    property pairs, and ``vector_search`` would then search the wrong nodes.
    ``ensure_vector_index`` and ``vector_search`` both call this function, so
    they always agree on the name.

    Args:
        label: The node label. Must already be validated.
        vector_property: The vector property name. Must already be validated.

    Returns:
        The index name ``ensure_vector_index`` and ``vector_search`` share.
    """
    validate_identifier(label)
    validate_identifier(vector_property)
    return f"idx_{len(label)}_{label}_{len(vector_property)}_{vector_property}_vector"


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
