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
