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
    """Build Cypher returning active match components from seed ids.

    Pending visibility is job-scoped, not a plain exclusion: the
    materialization pass runs inside its own job's pending phase and must
    see the entities and matches that same job just wrote, while still
    excluding every other in-flight job's. A null ``$job_id`` reduces both
    guards to committed-only, which is what every caller outside a job
    passes.

    Returns:
        Parameterized Cypher expecting $seed_ids (list of string ids) and
        $job_id (the in-flight job's id, or null outside a job). Returns
        each seed id with its distinct active component members.
    """
    return (
        "UNWIND $seed_ids AS seed_id "
        f"MATCH (seed:{NODE_IDENTITY_LABEL} {{id: seed_id}})"
        f"-[matches:{MATCHES_RELATION}*0..]-(member:{NODE_IDENTITY_LABEL}) "
        "WHERE ALL(match IN matches WHERE match.active = true) "
        "AND ALL(match IN matches WHERE match._pending_job_id IS NULL "
        "OR match._pending_job_id = $job_id) "
        "AND (seed._pending_job_id IS NULL OR seed._pending_job_id = $job_id) "
        "AND (member._pending_job_id IS NULL OR member._pending_job_id = $job_id) "
        "RETURN DISTINCT seed_id, member"
    )


def hydrate_resolved_entities_by_id_query() -> str:
    """Build Cypher hydrating materializations returned by vector search.

    Pending visibility is job-scoped: a null ``$job_id`` reduces the
    guard to committed-only, so retrieval never hydrates a
    ResolvedEntity an uncommitted job materialized.

    Returns:
        Parameterized Cypher expecting $ids (list of string ids) and
        $job_id (the in-flight job's id, or null outside a job).
    """
    return (
        "UNWIND $ids AS resolved_entity_id "
        f"MATCH (resolved:{RESOLVED_ENTITY_LABEL} {{id: resolved_entity_id}}) "
        "WHERE resolved.vector_sync_status = 'synced' "
        "AND (resolved._pending_job_id IS NULL "
        "OR resolved._pending_job_id = $job_id) "
        "RETURN resolved"
    )


def fetch_active_resolved_member_ids_query() -> str:
    """Build Cypher finding raw hits hidden by an active materialization.

    Pending visibility is job-scoped on both the edge and the resolved
    node: a null ``$job_id`` reduces both guards to committed-only, so
    an uncommitted job's materialization never hides a raw hit.

    Returns:
        Parameterized Cypher expecting $ids (list of string ids) and
        $job_id (the in-flight job's id, or null outside a job).
    """
    return (
        "UNWIND $ids AS entity_id "
        f"MATCH (entity:{NODE_IDENTITY_LABEL} {{id: entity_id}})"
        f"-[edge:{RESOLVED_AS_RELATION}]->(resolved:{RESOLVED_ENTITY_LABEL}) "
        "WHERE resolved.vector_sync_status = 'synced' "
        "AND (edge._pending_job_id IS NULL OR edge._pending_job_id = $job_id) "
        "AND (resolved._pending_job_id IS NULL "
        "OR resolved._pending_job_id = $job_id) "
        "RETURN entity_id"
    )


def fetch_active_matches_among_ids_query() -> str:
    """Build Cypher returning visible active match edges inside an id set."""
    return (
        "UNWIND $ids AS entity_id "
        f"MATCH (a:{NODE_IDENTITY_LABEL} {{id: entity_id}})"
        f"-[match:{MATCHES_RELATION}]->(b:{NODE_IDENTITY_LABEL}) "
        "WHERE match.active = true AND b.id IN $ids "
        "AND (a._pending_job_id IS NULL OR a._pending_job_id = $job_id) "
        "AND (b._pending_job_id IS NULL OR b._pending_job_id = $job_id) "
        "AND (match._pending_job_id IS NULL "
        "OR match._pending_job_id = $job_id) "
        "RETURN match.id AS match_id, a.id AS a_id, b.id AS b_id"
    )


def fetch_entities_with_open_evidence_query() -> str:
    """Build Cypher returning candidate ids with visible open evidence."""
    return (
        "UNWIND $ids AS entity_id "
        f"MATCH (chunk:{NODE_IDENTITY_LABEL}:Chunk)-[mention:MENTIONED_IN]->"
        f"(entity:{NODE_IDENTITY_LABEL} {{id: entity_id}}) "
        f"MATCH (document:{NODE_IDENTITY_LABEL}:Document)-[part:PART_OF]->(chunk) "
        "WHERE part.invalid_at IS NULL "
        "AND (chunk._pending_job_id IS NULL OR chunk._pending_job_id = $job_id) "
        "AND (mention._pending_job_id IS NULL "
        "OR mention._pending_job_id = $job_id) "
        "AND (entity._pending_job_id IS NULL OR entity._pending_job_id = $job_id) "
        "AND (document._pending_job_id IS NULL "
        "OR document._pending_job_id = $job_id) "
        "AND (part._pending_job_id IS NULL OR part._pending_job_id = $job_id) "
        "RETURN DISTINCT entity.id AS id"
    )


def fetch_entity_cluster_memberships_query() -> str:
    """Build Cypher returning visible cluster memberships for candidates."""
    return (
        "UNWIND $ids AS entity_id "
        f"MATCH (entity:{NODE_IDENTITY_LABEL} {{id: entity_id}})"
        f"-[membership:{RESOLVED_AS_RELATION}]->(resolved:{RESOLVED_ENTITY_LABEL}) "
        "WHERE (entity._pending_job_id IS NULL OR entity._pending_job_id = $job_id) "
        "AND (membership._pending_job_id IS NULL "
        "OR membership._pending_job_id = $job_id) "
        "AND (resolved._pending_job_id IS NULL "
        "OR resolved._pending_job_id = $job_id) "
        "RETURN entity_id, resolved.id AS resolved_id, "
        "resolved.member_ids AS member_ids"
    )
