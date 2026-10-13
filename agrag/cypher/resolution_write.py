"""Cypher writes for non-destructive entity resolution."""

from agrag.common.data_models.graph_record import PENDING_JOB_ID_PROPERTY
from agrag.common.data_models.resolved_entity import (
    MATCHES_RELATION,
    RESOLVED_AS_RELATION,
    RESOLVED_ENTITY_LABEL,
    RESOLVED_ENTITY_VECTOR_DELETION_LABEL,
)
from agrag.common.data_models.structure import HAS_PART
from agrag.cypher._pending_filter import pending_filter_clause
from agrag.cypher.entities import (
    MERGE_ALIAS_LABEL,
    NODE_IDENTITY_LABEL,
    own_row_expression,
)


def upsert_matches_query() -> str:
    """Build Cypher that idempotently records a confirmed entity match.

    A match the job creates carries that job's id, so component reads
    (which filter pending matches) never traverse uncommitted edges. A
    null ``$pending_job_id`` sets no property and applies to committed
    edges, as it did before jobs existed.

    Re-confirming a committed edge under a job is not applied: the row
    reports ``written`` false, and the store defers the update to the
    job's commit transaction. The edge stays inactive until then, so a
    reader never sees a job's decision before the job commits.

    Returns:
        Parameterized Cypher expecting $entity_a_id, $entity_b_id,
        $match_id, $comparator, $score, $reasoning, $decided_at, and
        $pending_job_id (the in-flight job's id, or null outside a job).
        It returns ``id`` and ``written`` for the matched edge.
    """
    own = own_row_expression("r", "$pending_job_id")
    return (
        f"MATCH (a:{NODE_IDENTITY_LABEL} {{id: $entity_a_id}}), "
        f"(b:{NODE_IDENTITY_LABEL} {{id: $entity_b_id}}) "
        f"MERGE (a)-[r:{MATCHES_RELATION} {{id: $match_id}}]->(b) "
        f"ON CREATE SET r.{PENDING_JOB_ID_PROPERTY} = $pending_job_id "
        f"WITH r, {own} AS own "
        "FOREACH (_ IN CASE WHEN own THEN [1] ELSE [] END | "
        "SET r.active = true, r.comparator = $comparator, r.score = $score, "
        "r.reasoning = $reasoning, r.decided_at = $decided_at) "
        "RETURN r.id AS id, own AS written"
    )


def deactivate_match_query() -> str:
    """Build Cypher that retains but deactivates a match edge."""
    return (
        f"MATCH ()-[r:{MATCHES_RELATION} {{id: $match_id}}]->() "
        f"WHERE {pending_filter_clause('r')} "
        "SET r.active = false RETURN r"
    )


def replace_component_resolved_entities_query() -> str:
    """Build Cypher replacing memberships outside a pending cutover.

    A pending cutover must not delete the previously committed
    resolved entity: rollback can remove only rows created by that cutover.
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
        "WITH resolved_entities "
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
    """Build Cypher deleting orphaned entities with a final evidence check."""
    return (
        "UNWIND $ids AS entity_id "
        f"MATCH (entity:{NODE_IDENTITY_LABEL} {{id: entity_id}}) "
        "WHERE NOT EXISTS { "
        f"MATCH (chunk:{NODE_IDENTITY_LABEL}:Chunk)-[:MENTIONED_IN]->(entity) "
        f"MATCH (document:{NODE_IDENTITY_LABEL}:Document)-[part:{HAS_PART}]->(chunk) "
        "WHERE part.invalid_at IS NULL } "
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
        f"MERGE (pending:{RESOLVED_ENTITY_VECTOR_DELETION_LABEL} {{id: record.id}}) "
        "SET pending.collection = record.collection, "
        "pending.error = record.error, pending.updated_at = datetime()"
    )


def clear_resolved_entity_vector_deletions_query() -> str:
    """Build Cypher removing successfully retried vector deletions."""
    return (
        "UNWIND $ids AS pending_id "
        f"MATCH (pending:{RESOLVED_ENTITY_VECTOR_DELETION_LABEL} {{id: pending_id}}) "
        "DETACH DELETE pending"
    )


def fetch_resolved_entity_vector_deletions_query() -> str:
    """Build Cypher reading vector deletions that still need a retry."""
    return (
        f"MATCH (pending:{RESOLVED_ENTITY_VECTOR_DELETION_LABEL}) "
        "RETURN pending.id AS id, pending.collection AS collection"
    )
