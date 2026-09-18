"""Cypher reads for local entity-resolution materialization."""

from agrag.common.data_models.resolved_entity import (
    MATCHES_RELATION,
    RESOLVED_AS_RELATION,
    RESOLVED_ENTITY_LABEL,
)
from agrag.cypher.entities import NODE_IDENTITY_LABEL


def fetch_matches_for_component_query() -> str:
    """Build Cypher returning active matches touching supplied entity ids."""
    return (
        "UNWIND $entity_ids AS entity_id "
        f"MATCH (a:{NODE_IDENTITY_LABEL} {{id: entity_id}})"
        f"-[match:{MATCHES_RELATION} {{active: true}}]-(b:{NODE_IDENTITY_LABEL}) "
        "RETURN DISTINCT a, b, match"
    )


def fetch_resolved_entity_members_query() -> str:
    """Build Cypher returning the members of one resolved entity."""
    return (
        f"MATCH (entity:{NODE_IDENTITY_LABEL})"
        f"-[:{RESOLVED_AS_RELATION}]->"
        f"(resolved:{RESOLVED_ENTITY_LABEL} {{id: $resolved_entity_id}}) "
        "RETURN entity"
    )


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
