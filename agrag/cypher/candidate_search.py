"""Cypher builders for lexical candidate search."""

from agrag.common.data_models.candidate import CANDIDATE_LABEL, EVIDENCED_BY
from agrag.common.data_models.graph_record import PENDING_JOB_ID_PROPERTY
from agrag.cypher.entities import NODE_IDENTITY_LABEL


def search_candidates_query() -> str:
    """Build a committed-evidence search grouped by candidate key and state."""
    return (
        f"MATCH (candidate:{CANDIDATE_LABEL}) "
        "WHERE candidate.state IN ['pending', 'approved'] "
        f"AND candidate.{PENDING_JOB_ID_PROPERTY} IS NULL "
        f"MATCH (candidate)-[evidence:{EVIDENCED_BY}]->"
        f"(chunk:{NODE_IDENTITY_LABEL}) "
        f"WHERE evidence.{PENDING_JOB_ID_PROPERTY} IS NULL "
        f"AND chunk.{PENDING_JOB_ID_PROPERTY} IS NULL "
        "WITH DISTINCT candidate "
        "WITH candidate.key AS key, candidate.state AS state, "
        "collect(candidate) AS nodes, sum(candidate.count) AS total "
        "WITH key, state, nodes, total, "
        "reduce(first = head(nodes), node IN nodes | "
        "CASE WHEN node.id < first.id THEN node ELSE first END) AS first, "
        "reduce(score = 0, term IN $terms | "
        "score + CASE WHEN any(node IN nodes WHERE "
        "(toLower(coalesce(node.label, '')) + ' ' + "
        "toLower(coalesce(node.text, '')) + ' ' + "
        "toLower(coalesce(node.source_text, '')) + ' ' + "
        "toLower(coalesce(node.target_text, ''))) CONTAINS term) "
        "THEN 1 ELSE 0 END) AS score "
        "WHERE score > 0 AND ($kind IS NULL OR first.kind = $kind) "
        "RETURN {id: first.id, kind: first.kind, label: first.label, "
        "text: coalesce(first.text, ''), source_text: first.source_text, "
        "target_text: first.target_text, confidence: first.confidence, "
        "reason: first.reason, chunk_id: first.chunk_id, state: state, "
        "count: total, schema_fingerprint: first.schema_fingerprint, "
        "source_entity_id: first.source_entity_id, "
        "target_entity_id: first.target_entity_id, "
        "source_label: first.source_label, target_label: first.target_label} "
        "AS candidate, score, total, key "
        "ORDER BY score DESC, total DESC, key ASC, state ASC LIMIT $limit"
    )
