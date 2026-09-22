"""Cypher writes for non-destructive entity resolution."""

from agrag.common.data_models.graph_record import PENDING_JOB_ID_PROPERTY
from agrag.common.data_models.resolved_entity import (
    MATCHES_RELATION,
    RESOLVED_AS_RELATION,
    RESOLVED_ENTITY_LABEL,
)
from agrag.cypher.entities import MERGE_ALIAS_LABEL, NODE_IDENTITY_LABEL


_PENDING_VECTOR_DELETION_LABEL = "ResolvedEntityVectorDeletion"


def upsert_matches_query() -> str:
    """Build Cypher that idempotently records a confirmed entity match.

    A match written by an in-flight Cutover Job carries that job's id, so
    component reads (which filter pending matches) never traverse
    uncommitted edges. A null ``$pending_job_id`` sets no property,
    preserving today's behavior for callers outside a job. Re-confirming
    an already-committed edge under a job re-tags it until that job
    commits, which is correct: the edge is under active revision.

    Returns:
        Parameterized Cypher expecting $entity_a_id, $entity_b_id,
        $match_id, $comparator, $score, $reasoning, $decided_at, and
        $pending_job_id (the in-flight job's id, or null outside a job).
    """
    return (
        f"MATCH (a:{NODE_IDENTITY_LABEL} {{id: $entity_a_id}}), "
        f"(b:{NODE_IDENTITY_LABEL} {{id: $entity_b_id}}) "
        f"MERGE (a)-[r:{MATCHES_RELATION} {{id: $match_id}}]->(b) "
        "ON CREATE SET r.active = true, r.comparator = $comparator, "
        "r.score = $score, r.reasoning = $reasoning, "
        "r.decided_at = $decided_at, "
        f"r.{PENDING_JOB_ID_PROPERTY} = $pending_job_id "
        "ON MATCH SET r.active = CASE WHEN $pending_job_id IS NULL "
        "THEN true ELSE r.active END, "
        "r.comparator = CASE WHEN $pending_job_id IS NULL "
        "THEN $comparator ELSE r.comparator END, "
        "r.score = CASE WHEN $pending_job_id IS NULL "
        "THEN $score ELSE r.score END, "
        "r.reasoning = CASE WHEN $pending_job_id IS NULL "
        "THEN $reasoning ELSE r.reasoning END, "
        "r.decided_at = CASE WHEN $pending_job_id IS NULL "
        "THEN $decided_at ELSE r.decided_at END "
        "RETURN r"
    )


def deactivate_match_query() -> str:
    """Build Cypher that retains but deactivates a match edge."""
    return (
        f"MATCH ()-[r:{MATCHES_RELATION} {{id: $match_id}}]->() "
        "SET r.active = false RETURN r"
    )


def replace_component_materializations_query() -> str:
    """Build Cypher replacing memberships outside a pending cutover.

    A pending cutover must not delete the previously committed
    materialization: rollback can remove only rows created by that cutover.
    The pending node remains alongside the old one until a later
    consolidation pass replaces it after commit.
    """
    return (
        "UNWIND CASE WHEN $pending_job_id IS NULL THEN $member_ids ELSE [] END "
        "AS member_id "
        f"MATCH (member:{NODE_IDENTITY_LABEL} {{id: member_id}})"
        f"-[membership:{RESOLVED_AS_RELATION}]->"
        f"(resolved:{RESOLVED_ENTITY_LABEL}) "
        "WITH collect(DISTINCT membership) AS memberships, "
        "collect(DISTINCT resolved) AS resolved_entities "
        "FOREACH (membership IN memberships | DELETE membership) "
        "UNWIND resolved_entities AS resolved "
        "WITH resolved, resolved.id AS resolved_id "
        f"OPTIONAL MATCH (remaining:{NODE_IDENTITY_LABEL})"
        f"-[:{RESOLVED_AS_RELATION}]->(resolved) "
        "WITH resolved, resolved_id, count(remaining) AS remaining_members "
        "FOREACH (_ IN CASE WHEN remaining_members = 0 THEN [1] ELSE [] END | "
        "DETACH DELETE resolved) "
        "RETURN collect(CASE WHEN remaining_members = 0 THEN resolved_id END) "
        "AS removed_resolved_entity_ids"
    )


def set_resolved_entity_sync_status_query() -> str:
    """Build Cypher setting the vector synchronization state of derived nodes."""
    return (
        "UNWIND $records AS record "
        f"MATCH (resolved:{RESOLVED_ENTITY_LABEL} {{id: record.id}}) "
        "SET resolved.vector_sync_status = record.status, "
        "resolved.vector_sync_error = record.error"
    )


def delete_entities_query() -> str:
    """Build Cypher deleting entities and their mention/cluster edges."""
    return (
        "UNWIND $ids AS entity_id "
        f"MATCH (entity:{NODE_IDENTITY_LABEL} {{id: entity_id}}) "
        "OPTIONAL MATCH (entity)-[mention:MENTIONED_IN]-() "
        f"OPTIONAL MATCH (entity)-[membership:{RESOLVED_AS_RELATION}]->"
        f"(:{RESOLVED_ENTITY_LABEL}) "
        "WITH entity, entity.id AS entity_id, "
        "collect(DISTINCT mention) AS mentions, "
        "collect(DISTINCT membership) AS memberships "
        "FOREACH (mention IN mentions | DELETE mention) "
        "FOREACH (membership IN memberships | DELETE membership) "
        "WITH entity, entity_id "
        "DETACH DELETE entity "
        "RETURN entity_id"
    )


def delete_resolved_entities_query() -> str:
    """Build Cypher deleting resolved nodes left with no members."""
    return (
        "UNWIND $ids AS resolved_id "
        f"MATCH (resolved:{RESOLVED_ENTITY_LABEL} {{id: resolved_id}}) "
        "DETACH DELETE resolved "
        "RETURN resolved_id"
    )


def delete_merge_aliases_for_entities_query() -> str:
    """Build Cypher deleting merge aliases owned by removed entities."""
    return (
        "UNWIND $ids AS entity_id "
        f"MATCH (alias:{MERGE_ALIAS_LABEL} {{entity_id: entity_id}}) "
        "WITH alias, alias.entity_id AS entity_id "
        "DETACH DELETE alias "
        "RETURN entity_id"
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
