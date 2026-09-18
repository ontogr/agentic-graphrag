"""Cypher for community retrieval reads."""

from agrag.common.data_models.community import COMMUNITY_LABEL, MEMBER_OF_RELATION
from agrag.cypher.entities import NODE_IDENTITY_LABEL


def communities_for_entities_query(where_clause: str = "") -> str:
    """Build Cypher finding communities overlapping given entity ids.

    Args:
        where_clause: Optional parameterized Cypher ``WHERE`` clause
            (including the ``WHERE`` keyword) applied to the candidate
            community node ``c``, e.g. from
            ``SearchFilters.to_cypher_where("c")``. Empty applies no
            additional constraint. Community nodes carry no document or
            tenant scope, so a document- or property-scoped filter that
            names a property Community nodes never have makes this
            clause match nothing, returning no communities rather than
            an unscoped one.

    Returns:
        Parameterized Cypher expecting $entity_ids (list of string ids)
        and $top_k (max rows to return; must be non-negative, since
        Neo4j rejects a negative LIMIT). Returns each overlapping
        community node and its overlap count, highest overlap first.
    """
    return (
        "UNWIND $entity_ids AS entity_id "
        f"MATCH (e:{NODE_IDENTITY_LABEL} {{id: entity_id}})"
        f"-[:{MEMBER_OF_RELATION}]->(c:{COMMUNITY_LABEL}) "
        f"{where_clause + ' ' if where_clause else ''}"
        "WITH c, count(DISTINCT entity_id) AS overlap "
        "RETURN c, overlap ORDER BY overlap DESC LIMIT $top_k"
    )
