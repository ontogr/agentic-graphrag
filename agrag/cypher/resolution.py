"""Cypher builders for the non-destructive semantic entity match graph."""

from agrag.cypher.entities import NODE_IDENTITY_LABEL


def active_component_query() -> str:
    """Return active raw component members reachable from the supplied seed ids."""
    return (
        f"UNWIND $seed_ids AS seed_id "
        f"MATCH (seed:{NODE_IDENTITY_LABEL} {{id: seed_id}}) "
        "MATCH path=(seed)-[:MATCHES*0..]-(member) "
        "WHERE ALL(edge IN relationships(path) WHERE edge.active = true) "
        "AND NOT member:ResolvedEntity "
        "RETURN DISTINCT member"
    )


def delete_component_materializations_query() -> str:
    """Return Cypher that removes current materializations for raw component members."""
    return (
        f"MATCH (member:{NODE_IDENTITY_LABEL}) "
        "WHERE member.id IN $member_ids "
        "OPTIONAL MATCH (member)-[membership:RESOLVED_AS]->(resolved:ResolvedEntity) "
        "WITH collect(DISTINCT membership) AS memberships, "
        "collect(DISTINCT resolved) AS resolved_nodes "
        "FOREACH (membership IN memberships | DELETE membership) "
        "FOREACH (resolved IN resolved_nodes | DETACH DELETE resolved)"
    )
