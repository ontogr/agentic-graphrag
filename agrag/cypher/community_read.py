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
        Parameterized Cypher expecting $entity_ids (list of string ids),
        $job_id (the in-flight Cutover Job's id, or null outside a job),
        and $top_k (max rows to return; must be non-negative, since
        Neo4j rejects a negative LIMIT). Returns each overlapping
        community node and its overlap count, highest overlap first.
        Community nodes are never written by a Cutover Job, but the
        member entity anchor is: the ``$job_id`` guard keeps a
        community from being found through a pending member edge.
    """
    filter_predicate = where_clause.removeprefix("WHERE ").strip()
    filter_suffix = f"AND {filter_predicate} " if filter_predicate else ""
    return (
        "UNWIND $entity_ids AS entity_id "
        f"MATCH (e:{NODE_IDENTITY_LABEL} {{id: entity_id}})"
        f"-[r:{MEMBER_OF_RELATION}]->(c:{COMMUNITY_LABEL}) "
        "WHERE r._pending_job_id IS NULL OR r._pending_job_id = $job_id "
        f"{filter_suffix}"
        "WITH c, count(DISTINCT entity_id) AS overlap "
        "RETURN c, overlap ORDER BY overlap DESC LIMIT $top_k"
    )
