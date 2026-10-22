"""Cypher reads for local entity-resolution rebuild."""

from agrag.common.data_models.resolved_entity import (
    MATCHES_RELATION,
    RESOLVED_AS_RELATION,
    RESOLVED_ENTITY_LABEL,
)
from agrag.common.data_models.structure import HAS_PART
from agrag.cypher._pending_filter import pending_filter_clause
from agrag.cypher.entities import NODE_IDENTITY_LABEL


def fetch_decided_pairs_query() -> str:
    """Return visible pairs with an active match or shared cluster."""
    return (
        "UNWIND $pairs AS pair "
        f"MATCH (a:{NODE_IDENTITY_LABEL} {{id: pair[0]}}) "
        f"MATCH (a)-[r:{MATCHES_RELATION}]-(b:{NODE_IDENTITY_LABEL} {{id: pair[1]}}) "
        "WHERE r.active = true "
        f"AND {pending_filter_clause('a', 'job_id')} "
        f"AND {pending_filter_clause('b', 'job_id')} "
        f"AND {pending_filter_clause('r', 'job_id')} "
        "RETURN a.id AS a_id, b.id AS b_id UNION "
        "UNWIND $pairs AS pair "
        f"MATCH (a:{NODE_IDENTITY_LABEL} {{id: pair[0]}})"
        f"-[first:{RESOLVED_AS_RELATION}]->(group:{RESOLVED_ENTITY_LABEL})"
        f"<-[second:{RESOLVED_AS_RELATION}]-(b:{NODE_IDENTITY_LABEL} {{id: pair[1]}}) "
        f"WHERE {pending_filter_clause('a', 'job_id')} "
        f"AND {pending_filter_clause('b', 'job_id')} "
        f"AND {pending_filter_clause('group', 'job_id')} "
        f"AND {pending_filter_clause('first', 'job_id')} "
        f"AND {pending_filter_clause('second', 'job_id')} "
        "RETURN a.id AS a_id, b.id AS b_id"
    )


def fetch_match_endpoints_query() -> str:
    """Build Cypher returning both endpoints of one match edge."""
    return (
        f"MATCH (a:{NODE_IDENTITY_LABEL})-"
        f"[match:{MATCHES_RELATION} {{id: $match_id}}]->"
        f"(b:{NODE_IDENTITY_LABEL}) "
        f"WHERE {pending_filter_clause('match')} "
        f"AND {pending_filter_clause('a')} AND {pending_filter_clause('b')} "
        "RETURN a, b"
    )


def fetch_visible_nodes_query() -> str:
    """Build Cypher returning the visible identity nodes among the given ids.

    Pending visibility is job-scoped: a null ``$job_id`` reduces the guard to
    committed-only.

    Returns:
        Parameterized Cypher expecting $ids (list of string ids) and $job_id.
        Returns each visible node as ``member`` with its ``id``.
    """
    return (
        "UNWIND $ids AS id "
        f"MATCH (n:{NODE_IDENTITY_LABEL} {{id: id}}) "
        f"WHERE {pending_filter_clause('n', 'job_id')} "
        "RETURN id, n AS member"
    )


def fetch_active_match_neighbors_query() -> str:
    """Build Cypher returning the entities one active match away from each id.

    Pending visibility is job-scoped, as in ``fetch_visible_nodes_query``: the
    rebuild pass runs inside its own job's pending phase and must see the
    entities and matches that same job just wrote, while excluding every other
    in-flight job's.

    Returns:
        Parameterized Cypher expecting $ids (list of string ids) and $job_id
        (the in-flight job's id, or null outside a job). Returns one row per
        active match edge: the start ``id``, the ``neighbor_id`` and the
        neighbor node as ``member``.
    """
    return (
        "UNWIND $ids AS id "
        f"MATCH (a:{NODE_IDENTITY_LABEL} {{id: id}})"
        f"-[match:{MATCHES_RELATION}]-(b:{NODE_IDENTITY_LABEL}) "
        "WHERE match.active = true "
        f"AND {pending_filter_clause('match', 'job_id')} "
        f"AND {pending_filter_clause('a', 'job_id')} "
        f"AND {pending_filter_clause('b', 'job_id')} "
        "RETURN DISTINCT id, b.id AS neighbor_id, b AS member"
    )


def fetch_committed_component_decided_at_query() -> str:
    """Build Cypher returning when each committed match of a component was decided.

    Reads the active committed matches between the given members directly,
    so the cost does not depend on how many paths join them.

    Returns:
        Parameterized Cypher expecting $member_ids (list of string ids).
        Returns one row per distinct ``decided_at`` value among the active,
        committed matches whose two ends are both members.
    """
    return (
        f"MATCH (a:{NODE_IDENTITY_LABEL})-[match:{MATCHES_RELATION}]->"
        f"(b:{NODE_IDENTITY_LABEL}) "
        "WHERE a.id IN $member_ids AND b.id IN $member_ids "
        "AND match.active = true AND match._pending_job_id IS NULL "
        "RETURN DISTINCT match.decided_at AS decided_at"
    )


def load_resolved_entities_by_id_query() -> str:
    """Build Cypher that loads resolved entities returned by vector search.

    Pending visibility is job-scoped: a null ``$job_id`` reduces the
    guard to committed-only, so retrieval never loads a
    ResolvedEntity an uncommitted job rebuilt.

    Returns:
        Parameterized Cypher expecting $ids (list of string ids) and
        $job_id (the in-flight job's id, or null outside a job).
    """
    return (
        "UNWIND $ids AS resolved_entity_id "
        f"MATCH (resolved:{RESOLVED_ENTITY_LABEL} {{id: resolved_entity_id}}) "
        "WHERE resolved.vector_sync_status = 'synced' "
        f"AND {pending_filter_clause('resolved', 'job_id')} "
        "RETURN resolved"
    )


def load_resolved_entities_for_sync_query() -> str:
    """Build Cypher loading committed resolved entities regardless of sync status."""
    return (
        "UNWIND $ids AS resolved_entity_id "
        f"MATCH (resolved:{RESOLVED_ENTITY_LABEL} {{id: resolved_entity_id}}) "
        f"WHERE {pending_filter_clause('resolved')} "
        "RETURN resolved"
    )


def fetch_active_resolved_member_ids_query() -> str:
    """Build Cypher finding raw hits hidden by an active resolved entity.

    Pending visibility is job-scoped on both the edge and the resolved
    node: a null ``$job_id`` reduces both guards to committed-only, so
    an uncommitted job's resolved entity never hides a raw hit.

    Returns:
        Parameterized Cypher expecting $ids (list of string ids) and
        $job_id (the in-flight job's id, or null outside a job).
    """
    return (
        "UNWIND $ids AS entity_id "
        f"MATCH (entity:{NODE_IDENTITY_LABEL} {{id: entity_id}})"
        f"-[edge:{RESOLVED_AS_RELATION}]->(resolved:{RESOLVED_ENTITY_LABEL}) "
        "WHERE resolved.vector_sync_status = 'synced' "
        f"AND {pending_filter_clause('edge', 'job_id')} "
        f"AND {pending_filter_clause('resolved', 'job_id')} "
        "RETURN entity_id"
    )


def fetch_active_matches_among_ids_query() -> str:
    """Build Cypher returning visible active match edges inside an id set."""
    return (
        "UNWIND $ids AS entity_id "
        f"MATCH (a:{NODE_IDENTITY_LABEL} {{id: entity_id}})"
        f"-[match:{MATCHES_RELATION}]->(b:{NODE_IDENTITY_LABEL}) "
        "WHERE match.active = true AND b.id IN $ids "
        f"AND {pending_filter_clause('a', 'job_id')} "
        f"AND {pending_filter_clause('b', 'job_id')} "
        f"AND {pending_filter_clause('match', 'job_id')} "
        "RETURN match.id AS match_id, a.id AS a_id, b.id AS b_id"
    )


def fetch_entities_with_open_evidence_query() -> str:
    """Build Cypher returning candidate ids with visible open evidence.

    A null ``$job_id`` only counts committed evidence. A rebuild
    pass can instead supply its own pending job id to see its new writes.
    """
    return (
        "UNWIND $ids AS entity_id "
        f"MATCH (chunk:{NODE_IDENTITY_LABEL}:Chunk)-[mention:MENTIONED_IN]->"
        f"(entity:{NODE_IDENTITY_LABEL} {{id: entity_id}}) "
        f"MATCH (document:{NODE_IDENTITY_LABEL}:Document)-[part:{HAS_PART}]->(chunk) "
        "WHERE part.invalid_at IS NULL "
        f"AND {pending_filter_clause('entity', 'job_id')} "
        f"AND {pending_filter_clause('chunk', 'job_id')} "
        f"AND {pending_filter_clause('mention', 'job_id')} "
        f"AND {pending_filter_clause('document', 'job_id')} "
        f"AND {pending_filter_clause('part', 'job_id')} "
        "RETURN DISTINCT entity.id AS id"
    )


def fetch_entity_cluster_memberships_query() -> str:
    """Build Cypher returning visible cluster memberships for candidates."""
    return (
        "UNWIND $ids AS entity_id "
        f"MATCH (entity:{NODE_IDENTITY_LABEL} {{id: entity_id}})"
        f"-[membership:{RESOLVED_AS_RELATION}]->(resolved:{RESOLVED_ENTITY_LABEL}) "
        f"WHERE {pending_filter_clause('entity', 'job_id')} "
        f"AND {pending_filter_clause('membership', 'job_id')} "
        f"AND {pending_filter_clause('resolved', 'job_id')} "
        "RETURN entity_id, resolved.id AS resolved_id, "
        "resolved.member_ids AS member_ids"
    )
