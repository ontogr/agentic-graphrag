"""Cypher reads for local entity-resolution materialization."""

from agrag.common.data_models.resolved_entity import (
    MATCHES_RELATION,
    RESOLVED_AS_RELATION,
    RESOLVED_ENTITY_LABEL,
)
from agrag.cypher.entities import NODE_IDENTITY_LABEL


def fetch_match_endpoints_query() -> str:
    """Build Cypher returning both endpoints of one match edge."""
    return (
        f"MATCH (a:{NODE_IDENTITY_LABEL})-"
        f"[match:{MATCHES_RELATION} {{id: $match_id}}]->"
        f"(b:{NODE_IDENTITY_LABEL}) RETURN a, b"
    )


def fetch_active_component_members_query() -> str:
    """Build Cypher returning active match components from seed ids."""
    return (
        "UNWIND $seed_ids AS seed_id "
        f"MATCH (seed:{NODE_IDENTITY_LABEL} {{id: seed_id}})"
        f"-[matches:{MATCHES_RELATION}*0..]-(member:{NODE_IDENTITY_LABEL}) "
        "WHERE ALL(match IN matches WHERE match.active = true) "
        "RETURN DISTINCT seed_id, member"
    )


def hydrate_resolved_entities_by_id_query() -> str:
    """Build Cypher hydrating materializations returned by vector search."""
    return (
        "UNWIND $ids AS resolved_entity_id "
        f"MATCH (resolved:{RESOLVED_ENTITY_LABEL} {{id: resolved_entity_id}}) "
        "WHERE resolved.vector_sync_status = 'synced' "
        "RETURN resolved"
    )


def fetch_active_resolved_member_ids_query() -> str:
    """Build Cypher finding raw hits hidden by an active materialization."""
    return (
        "UNWIND $ids AS entity_id "
        f"MATCH (entity:{NODE_IDENTITY_LABEL} {{id: entity_id}})"
        f"-[:{RESOLVED_AS_RELATION}]->(resolved:{RESOLVED_ENTITY_LABEL}) "
        "WHERE resolved.vector_sync_status = 'synced' "
        "RETURN entity_id"
    )


def fetch_active_matches_among_ids_query() -> str:
    """Build Cypher returning active match edges inside an id set."""
    return (
        "UNWIND $ids AS entity_id "
        f"MATCH (a:{NODE_IDENTITY_LABEL} {{id: entity_id}})"
        f"-[match:{MATCHES_RELATION}]->(b:{NODE_IDENTITY_LABEL}) "
        "WHERE match.active = true AND b.id IN $ids "
        "RETURN match.id AS match_id, a.id AS a_id, b.id AS b_id"
    )


def fetch_entities_with_open_evidence_query() -> str:
    """Build Cypher returning candidate ids mentioned by an open chunk."""
    return (
        "UNWIND $ids AS entity_id "
        f"MATCH (chunk:{NODE_IDENTITY_LABEL}:Chunk)-[:MENTIONED_IN]->"
        f"(entity:{NODE_IDENTITY_LABEL} {{id: entity_id}}) "
        f"MATCH (document:{NODE_IDENTITY_LABEL}:Document)-[part:PART_OF]->(chunk) "
        "WHERE part.invalid_at IS NULL "
        "RETURN DISTINCT entity.id AS id"
    )


def fetch_entity_cluster_memberships_query() -> str:
    """Build Cypher returning each candidate's cluster and its members."""
    return (
        "UNWIND $ids AS entity_id "
        f"MATCH (entity:{NODE_IDENTITY_LABEL} {{id: entity_id}})"
        f"-[membership:{RESOLVED_AS_RELATION}]->(resolved:{RESOLVED_ENTITY_LABEL}) "
        "RETURN entity_id, resolved.id AS resolved_id, "
        "resolved.member_ids AS member_ids"
    )
