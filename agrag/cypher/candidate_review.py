"""Parameterized Cypher builders for candidate review operations."""

from agrag.common.data_models.candidate import CANDIDATE_LABEL, EVIDENCED_BY
from agrag.common.data_models.document import DOCUMENT_LABEL
from agrag.common.data_models.structure import HAS_PART
from agrag.cypher._pending_filter import pending_filter_clause
from agrag.cypher.entities import MERGE_ALIAS_LABEL, NODE_IDENTITY_LABEL


def list_candidates_query() -> str:
    """Return candidate groups with summed counts and distinct evidence."""
    return (
        f"MATCH (c:{CANDIDATE_LABEL}) WHERE {pending_filter_clause('c')} "
        "AND ($kind IS NULL OR c.kind = $kind) "
        "AND ($label IS NULL OR c.label = $label) "
        "AND ($state IS NULL OR c.state = $state) "
        "WITH c.key AS key, c.state AS state, collect(c) AS nodes, "
        "sum(c.count) AS total, max(c.confidence) AS best "
        "WHERE total >= $min_count "
        "CALL { WITH nodes UNWIND nodes AS n "
        f"OPTIONAL MATCH (n)-[evidence:{EVIDENCED_BY}]->"
        f"(chunk:{NODE_IDENTITY_LABEL}) "
        f"WHERE {pending_filter_clause('evidence')} "
        f"AND {pending_filter_clause('chunk')} "
        f"OPTIONAL MATCH (doc:{DOCUMENT_LABEL})-[part:{HAS_PART}]->(chunk) "
        f"WHERE {pending_filter_clause('part')} "
        f"AND {pending_filter_clause('doc')} "
        "RETURN collect(DISTINCT chunk.id) AS chunk_ids, "
        "collect(DISTINCT doc.id) AS document_ids } "
        "WITH key, state, total, best, nodes, chunk_ids, document_ids, "
        "reduce(first = head(nodes), n IN nodes | "
        "CASE WHEN n.id < first.id THEN n ELSE first END) AS first "
        "RETURN key, state, total AS count, [n IN nodes | n.id] AS ids, "
        "properties(first) AS candidate, best AS confidence, chunk_ids, "
        "size(document_ids) AS document_count "
        "ORDER BY count DESC, confidence DESC, key SKIP $skip LIMIT $limit"
    )


def select_candidate_keys_query() -> str:
    """Return distinct matching candidate keys, filtered by aggregate count."""
    return (
        f"MATCH (c:{CANDIDATE_LABEL}) WHERE {pending_filter_clause('c')} "
        "AND ($kind IS NULL OR c.kind = $kind) "
        "AND ($label IS NULL OR c.label = $label) "
        "AND ($state IS NULL OR c.state = $state) "
        "WITH c.key AS key, sum(c.count) AS total WHERE total >= $min_count "
        "RETURN key ORDER BY key"
    )


def select_candidate_ids_query() -> str:
    """Return candidate node ids matching a candidate filter."""
    return (
        f"MATCH (c:{CANDIDATE_LABEL}) WHERE {pending_filter_clause('c')} "
        "AND ($kind IS NULL OR c.kind = $kind) "
        "AND ($label IS NULL OR c.label = $label) "
        "AND ($state IS NULL OR c.state = $state) "
        "WITH c.key AS key, collect(c) AS nodes, sum(c.count) AS total "
        "WHERE total >= $min_count UNWIND nodes AS c RETURN c.id AS id ORDER BY id"
    )


def load_candidates_query() -> str:
    """Load individual candidate records by node id."""
    return (
        f"UNWIND $ids AS id MATCH (c:{CANDIDATE_LABEL} {{id: id}}) "
        f"WHERE {pending_filter_clause('c')} "
        "RETURN properties(c) AS candidate, c.key AS stored_key"
    )


def approved_group_ids_query() -> str:
    """Return all approved candidate ids in the transitioned groups."""
    return (
        f"MATCH (c:{CANDIDATE_LABEL}) WHERE c.key IN $keys "
        "AND c.state = 'approved' "
        f"AND {pending_filter_clause('c')} RETURN c.id AS id ORDER BY id"
    )


def transition_candidates_query() -> str:
    """Compare-and-swap candidate states, optionally storing resolved endpoints."""
    return (
        "UNWIND $rows AS row "
        f"MATCH (same_key:{CANDIDATE_LABEL} {{key: row.key}}) "
        "WITH row, same_key ORDER BY same_key.id "
        "WITH row, collect(same_key) AS same_key_candidates "
        "FOREACH (candidate IN same_key_candidates | "
        "SET candidate.id = candidate.id) "
        "WITH row, [candidate IN same_key_candidates | candidate.id] AS ids "
        "UNWIND ids AS id "
        f"MATCH (c:{CANDIDATE_LABEL} {{id: id}}) "
        f"WHERE c.key = row.key AND {pending_filter_clause('c')} "
        "AND c.state IN $from_states "
        "SET c.state = $to_state, c.decided_at = $decided_at, "
        "c.source_entity_id = coalesce(row.source_entity_id, c.source_entity_id), "
        "c.target_entity_id = coalesce(row.target_entity_id, c.target_entity_id) "
        "RETURN DISTINCT c.key AS key"
    )


def entity_labels_query() -> str:
    """Read committed non-candidate entity labels by id."""
    return (
        f"UNWIND $ids AS id MATCH (e:{NODE_IDENTITY_LABEL} {{id: id}}) "
        f"WHERE {pending_filter_clause('e')} AND NOT e:{CANDIDATE_LABEL} "
        "RETURN e.id AS id, labels(e) AS labels"
    )


def alias_owners_query() -> str:
    """Find committed entity owners for normalized merge keys."""
    return (
        f"UNWIND $merge_keys AS merge_key MATCH (a:{MERGE_ALIAS_LABEL} "
        "{merge_key: merge_key}) "
        f"WHERE {pending_filter_clause('a')} RETURN merge_key, a.entity_id AS entity_id"
    )


def match_prunable_query() -> str:
    """Count rejected and stale or low-count pending candidate groups."""
    return (
        f"MATCH (c:{CANDIDATE_LABEL}) WHERE {pending_filter_clause('c')} "
        "WITH c.key AS key, c.state AS state, collect(c) AS nodes, "
        "sum(c.count) AS total, max(c.created_at) AS newest "
        "WHERE state <> 'approved' AND (($rejected AND state = 'rejected') OR "
        "(state = 'pending' AND (($older_than IS NOT NULL AND "
        "newest < $older_than) OR ($below_count IS NOT NULL AND "
        "total < $below_count)))) RETURN count(key) AS matched"
    )


def delete_prunable_query() -> str:
    """Delete candidate groups selected by the prune criteria."""
    return (
        f"MATCH (c:{CANDIDATE_LABEL}) WHERE {pending_filter_clause('c')} "
        "WITH c.key AS key, c.state AS state, collect(c) AS nodes, "
        "sum(c.count) AS total, max(c.created_at) AS newest "
        "WHERE state <> 'approved' AND (($rejected AND state = 'rejected') OR "
        "(state = 'pending' AND (($older_than IS NOT NULL AND "
        "newest < $older_than) OR ($below_count IS NOT NULL AND "
        "total < $below_count)))) UNWIND nodes AS node DETACH DELETE node "
        "WITH DISTINCT key RETURN count(key) AS deleted"
    )
