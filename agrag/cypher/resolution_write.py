"""Cypher writes for non-destructive entity resolution."""

from agrag.common.data_models.resolved_entity import (
    MATCHES_RELATION,
    RESOLVED_AS_RELATION,
    RESOLVED_ENTITY_LABEL,
)
from agrag.cypher.entities import NODE_IDENTITY_LABEL


_PENDING_VECTOR_DELETION_LABEL = "ResolvedEntityVectorDeletion"


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


def replace_component_materializations_query() -> str:
    """Build Cypher deleting prior materializations for supplied raw members."""
    return (
        "UNWIND $member_ids AS member_id "
        f"MATCH (member:{NODE_IDENTITY_LABEL} {{id: member_id}})"
        f"-[membership:{RESOLVED_AS_RELATION}]->"
        f"(resolved:{RESOLVED_ENTITY_LABEL}) "
        "WITH collect(DISTINCT membership) AS memberships, "
        "collect(DISTINCT resolved) AS resolved_entities, "
        "collect(DISTINCT resolved.id) AS removed_resolved_entity_ids "
        "FOREACH (membership IN memberships | DELETE membership) "
        "FOREACH (resolved IN resolved_entities | DETACH DELETE resolved) "
        "RETURN removed_resolved_entity_ids"
    )


def set_resolved_entity_sync_status_query() -> str:
    """Build Cypher setting the vector synchronization state of derived nodes."""
    return (
        "UNWIND $records AS record "
        f"MATCH (resolved:{RESOLVED_ENTITY_LABEL} {{id: record.id}}) "
        "SET resolved.vector_sync_status = record.status, "
        "resolved.vector_sync_error = record.error"
    )


def enqueue_resolved_entity_vector_deletions_query() -> str:
    """Build Cypher persisting vector ids whose deletion needs a retry."""
    return (
        "UNWIND $records AS record "
        f"MERGE (pending:{_PENDING_VECTOR_DELETION_LABEL} {{id: record.id}}) "
        "SET pending.collection = record.collection, "
        "pending.error = record.error, pending.updated_at = datetime()"
    )


def clear_resolved_entity_vector_deletions_query() -> str:
    """Build Cypher removing successfully retried vector deletions."""
    return (
        "UNWIND $ids AS pending_id "
        f"MATCH (pending:{_PENDING_VECTOR_DELETION_LABEL} {{id: pending_id}}) "
        "DETACH DELETE pending"
    )


def fetch_resolved_entity_vector_deletions_query() -> str:
    """Build Cypher reading vector deletions that still need a retry."""
    return (
        f"MATCH (pending:{_PENDING_VECTOR_DELETION_LABEL}) "
        "RETURN pending.id AS id, pending.collection AS collection"
    )
