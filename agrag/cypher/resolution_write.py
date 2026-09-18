"""Cypher writes for non-destructive entity resolution."""

from agrag.common.data_models.resolved_entity import (
    MATCHES_RELATION,
    RESOLVED_AS_RELATION,
    RESOLVED_ENTITY_LABEL,
)
from agrag.cypher.entities import NODE_IDENTITY_LABEL


def upsert_matches_query() -> str:
    """Build Cypher that idempotently records a confirmed entity match."""
    return (
        f"MATCH (a:{NODE_IDENTITY_LABEL} {{id: $entity_a_id}}), "
        f"(b:{NODE_IDENTITY_LABEL} {{id: $entity_b_id}}) "
        f"OPTIONAL MATCH (a)-[existing:{MATCHES_RELATION} {{id: $match_id}}]-(b) "
        "DELETE existing "
        f"MERGE (a)-[r:{MATCHES_RELATION} {{id: $match_id}}]->(b) "
        "SET r.active = true, r.comparator = $comparator, r.score = $score, "
        "r.reasoning = $reasoning, r.decided_at = $decided_at "
        "RETURN r"
    )


def deactivate_match_query() -> str:
    """Build Cypher that retains but deactivates a match edge."""
    return (
        f"MATCH ()-[r:{MATCHES_RELATION} {{id: $match_id}}]->() "
        "SET r.active = false RETURN r"
    )


def upsert_resolved_as_query() -> str:
    """Build Cypher linking a member to its materialized resolved entity."""
    return (
        f"MATCH (e:{NODE_IDENTITY_LABEL} {{id: $entity_id}}), "
        f"(r:{RESOLVED_ENTITY_LABEL} {{id: $resolved_entity_id}}) "
        f"MERGE (e)-[edge:{RESOLVED_AS_RELATION}]->(r) "
        "RETURN edge"
    )


def delete_resolved_as_query() -> str:
    """Build Cypher deleting materialized membership edges by cluster id."""
    return (
        f"MATCH ()-[edge:{RESOLVED_AS_RELATION}]->"
        f"(r:{RESOLVED_ENTITY_LABEL} {{id: $resolved_entity_id}}) "
        "DELETE edge"
    )


def replace_component_materializations_query() -> str:
    """Build Cypher deleting prior materializations for supplied raw members."""
    return (
        "UNWIND $member_ids AS member_id "
        f"MATCH (member:{NODE_IDENTITY_LABEL} {{id: member_id}})"
        f"-[membership:{RESOLVED_AS_RELATION}]->"
        f"(resolved:{RESOLVED_ENTITY_LABEL}) "
        "WITH collect(DISTINCT membership) AS memberships, "
        "collect(DISTINCT resolved) AS resolved_entities "
        "FOREACH (membership IN memberships | DELETE membership) "
        "FOREACH (resolved IN resolved_entities | DETACH DELETE resolved)"
    )
