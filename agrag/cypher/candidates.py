"""Cypher builders for the isolated candidate graph store."""

from agrag.common.data_models.candidate import (
    CANDIDATE_LABEL,
    EVIDENCED_BY,
    SOURCE,
    TARGET,
)
from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.document import DOCUMENT_LABEL
from agrag.common.data_models.graph_record import PENDING_JOB_ID_PROPERTY
from agrag.common.data_models.graph_schema import RESERVED_ENTITY_LABELS
from agrag.common.data_models.structure import HAS_PART
from agrag.cypher._pending_filter import pending_filter_clause
from agrag.cypher.entities import NODE_IDENTITY_LABEL


def _created_tag(alias: str) -> str:
    return f"{alias}.{PENDING_JOB_ID_PROPERTY} = record.pending_job_id"


def _link(entity: str, edge_type: str, edge_id: str) -> str:
    return (
        f"FOREACH (_ IN CASE WHEN {entity} IS NULL THEN [] ELSE [1] END | "
        f"MERGE (c)-[{entity}_link:{edge_type} {{id: record.{edge_id}}}]->({entity}) "
        f"ON CREATE SET {_created_tag(f'{entity}_link')}) "
    )


def _visible_to_job(alias: str) -> str:
    """Match rows committed, or tagged with the candidate's own job."""
    property_ref = f"{alias}.{PENDING_JOB_ID_PROPERTY}"
    return f"({property_ref} IS NULL OR {property_ref} = record.pending_job_id)"


def _entity_only(alias: str) -> str:
    """Match a node that is an entity, not a document, chunk or other structure."""
    # Every entity carries NODE_IDENTITY_LABEL, so it is not a rejection signal.
    structural = RESERVED_ENTITY_LABELS - {NODE_IDENTITY_LABEL}
    reserved = ", ".join(f"'{label}'" for label in sorted(structural))
    return f"NONE(label IN labels({alias}) WHERE label IN [{reserved}])"


def upsert_candidates_query() -> str:
    """Build the batched, create-only candidate writer.

    A record writes nothing unless its chunk and every non-null endpoint
    resolve to committed rows or rows of its own job. A record that does
    not resolve returns no row, so the store reports it as a failure.
    """
    return (
        "UNWIND $records AS record "
        f"MATCH (chunk:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} "
        "{id: record.chunk_id}) "
        f"WHERE {_visible_to_job('chunk')} "
        f"OPTIONAL MATCH (source:{NODE_IDENTITY_LABEL} "
        "{id: record.source_entity_id}) "
        f"WHERE {_visible_to_job('source')} AND {_entity_only('source')} "
        f"OPTIONAL MATCH (target:{NODE_IDENTITY_LABEL} "
        "{id: record.target_entity_id}) "
        f"WHERE {_visible_to_job('target')} AND {_entity_only('target')} "
        "WITH record, chunk, source, target "
        "WHERE (record.source_entity_id IS NULL OR source IS NOT NULL) "
        "AND (record.target_entity_id IS NULL OR target IS NOT NULL) "
        f"MERGE (c:{CANDIDATE_LABEL} {{id: record.candidate_id}}) "
        f"ON CREATE SET c += record.properties, {_created_tag('c')} "
        f"MERGE (c)-[evidence:{EVIDENCED_BY} {{id: record.id}}]->(chunk) "
        f"ON CREATE SET {_created_tag('evidence')} "
        "WITH c, record, source, target "
        f"{_link('source', SOURCE, 'source_edge_id')}"
        f"{_link('target', TARGET, 'target_edge_id')}"
        "RETURN record.id AS id"
    )


def blocked_candidate_keys_query() -> str:
    """Build a lookup for keys with a committed reviewed candidate."""
    return (
        "UNWIND $keys AS key "
        f"MATCH (c:{CANDIDATE_LABEL} {{key: key}}) "
        f"WHERE c.state <> 'pending' AND {pending_filter_clause('c')} "
        "RETURN DISTINCT c.key AS key"
    )


def list_candidates_query() -> str:
    """Build a key-aggregating candidate list with optional filters."""
    return (
        f"MATCH (c:{CANDIDATE_LABEL}) "
        f"WHERE {pending_filter_clause('c', 'job_id')} "
        "AND ($kind IS NULL OR c.kind = $kind) "
        "AND ($label IS NULL OR c.label = $label) "
        "AND ($state IS NULL OR c.state = $state) "
        "WITH c.key AS key, c.state AS state, collect(c) AS nodes, "
        "sum(c.count) AS total, max(c.confidence) AS best "
        "WHERE total >= $min_count "
        "CALL (nodes) { UNWIND nodes AS n "
        f"OPTIONAL MATCH (n)-[e:{EVIDENCED_BY}]->(chunk:{NODE_IDENTITY_LABEL}) "
        f"WHERE {pending_filter_clause('e', 'job_id')} "
        f"AND {pending_filter_clause('chunk', 'job_id')} "
        "RETURN collect(DISTINCT chunk.id) AS chunk_ids } "
        "WITH key, state, total, best, chunk_ids, nodes, "
        "reduce(first = head(nodes), n IN nodes | "
        "CASE WHEN n.id < first.id THEN n ELSE first END) AS first "
        "RETURN key, state, first.kind AS kind, first.label AS label, "
        "first.text AS text, first.source_text AS source_text, "
        "first.source_label AS source_label, first.target_label AS target_label, "
        "first.target_text AS target_text, first.reason AS reason, "
        "first.schema_fingerprint AS schema_fingerprint, "
        "first.source_entity_id AS source_entity_id, "
        "first.target_entity_id AS target_entity_id, total AS count, "
        "best AS confidence, [n IN nodes | n.id] AS ids, chunk_ids "
        "ORDER BY total DESC, key SKIP $skip LIMIT $limit"
    )


def delete_reviewed_job_candidates_query() -> str:
    """Remove job candidates whose keys were reviewed before publication."""
    return (
        f"MATCH (candidate:{CANDIDATE_LABEL}) "
        f"WHERE candidate.{PENDING_JOB_ID_PROPERTY} = $job_id "
        "AND candidate.state = 'pending' "
        f"MATCH (reviewed:{CANDIDATE_LABEL} {{key: candidate.key}}) "
        "WHERE reviewed.state IN ['approved', 'rejected'] "
        f"AND reviewed.{PENDING_JOB_ID_PROPERTY} IS NULL "
        "WITH collect(DISTINCT candidate) AS duplicates "
        "FOREACH (candidate IN duplicates | DETACH DELETE candidate) "
        "RETURN size(duplicates) AS removed"
    )


def delete_stale_candidates_query() -> str:
    """Build deletion of committed pending candidates for a document."""
    return (
        f"MATCH (document:{NODE_IDENTITY_LABEL}:{DOCUMENT_LABEL} "
        "{id: $document_node_id})"
        f"-[:{HAS_PART}]->(chunk:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL}) "
        f"MATCH (candidate:{CANDIDATE_LABEL})-[:{EVIDENCED_BY}]->(chunk) "
        "WHERE candidate.state = 'pending' "
        f"AND candidate.{PENDING_JOB_ID_PROPERTY} IS NULL "
        "WITH collect(DISTINCT candidate) AS stale "
        "FOREACH (candidate IN stale | DETACH DELETE candidate) "
        "RETURN size(stale) AS removed"
    )
