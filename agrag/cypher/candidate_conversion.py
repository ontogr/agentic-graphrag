"""Cypher builders for converting reviewed candidates into graph data."""

from collections.abc import Sequence

from agrag.common.data_models.candidate import (
    CANDIDATE_LABEL,
    EVIDENCED_BY,
    SOURCE,
    TARGET,
)
from agrag.cypher._pending_filter import pending_filter_clause
from agrag.cypher.entities import (
    MERGE_ALIAS_LABEL,
    NODE_IDENTITY_LABEL,
    validate_identifier,
)


def approved_evidence_query() -> str:
    """Read approved candidate properties and their evidence chunk ids."""
    return (
        f"UNWIND $ids AS id MATCH (c:{CANDIDATE_LABEL} "
        "{id: id, state: 'approved'}) "
        f"WHERE {pending_filter_clause('c')} "
        f"OPTIONAL MATCH (c)-[evidence:{EVIDENCED_BY}]->"
        f"(chunk:{NODE_IDENTITY_LABEL}) "
        f"WHERE {pending_filter_clause('evidence')} "
        f"AND {pending_filter_clause('chunk')} "
        "RETURN c AS candidate, collect(DISTINCT chunk.id) AS chunk_ids"
    )


def alias_owners_query() -> str:
    """Find entities that already own any requested merge key."""
    return (
        f"UNWIND $merge_keys AS merge_key MATCH (alias:{MERGE_ALIAS_LABEL} "
        "{merge_key: merge_key}) "
        f"WHERE {pending_filter_clause('alias')} "
        f"MATCH (entity:{NODE_IDENTITY_LABEL} {{id: alias.entity_id}}) "
        f"WHERE {pending_filter_clause('entity')} "
        "RETURN alias.merge_key AS merge_key, alias.entity_id AS entity_id"
    )


def entity_labels_query() -> str:
    """Read labels for entities referenced by candidate endpoints."""
    return (
        f"UNWIND $ids AS id MATCH (entity:{NODE_IDENTITY_LABEL} {{id: id}}) "
        f"WHERE {pending_filter_clause('entity')} "
        "RETURN entity.id AS id, labels(entity) AS labels"
    )


def convert_entity_candidates_query(
    labels: Sequence[str], *, embedding_value: str = "row.embedding"
) -> str:
    """Turn each approved entity candidate into its identity node in place.

    Args:
        labels: The labels the converted entity node carries.
        embedding_value: The Cypher expression that stores the candidate's
            embedding on the entity. Backends that need a typed vector pass
            ``GraphStore.vector_value("row.embedding")``.
    """
    if not labels:
        raise ValueError("at least one entity label is required")
    label_clause = ":".join(validate_identifier(label) for label in labels)
    return (
        f"UNWIND $rows AS row MATCH (c:{CANDIDATE_LABEL} "
        "{id: row.id, kind: 'entity', state: 'approved'}) "
        f"WHERE {pending_filter_clause('c')} "
        f"OPTIONAL MATCH (c)-[evidence:{EVIDENCED_BY}]->"
        f"(chunk:{NODE_IDENTITY_LABEL}) "
        "WITH c, row, collect(DISTINCT chunk) AS chunks, "
        "collect(DISTINCT evidence) AS evidence_edges "
        f"WHERE ALL(chunk IN chunks WHERE {pending_filter_clause('chunk')}) "
        f"AND ALL(edge IN evidence_edges WHERE {pending_filter_clause('edge')}) "
        f"OPTIONAL MATCH (c)-[candidate_edge:{SOURCE}|{TARGET}]-() "
        "WITH c, row, chunks, evidence_edges, "
        "collect(DISTINCT candidate_edge) AS candidate_edges "
        f"WHERE ALL(edge IN candidate_edges WHERE {pending_filter_clause('edge')}) "
        "AND ALL(node IN [endpoint IN candidate_edges | startNode(endpoint)] "
        f"WHERE {pending_filter_clause('node')}) "
        "AND ALL(node IN [endpoint IN candidate_edges | endNode(endpoint)] "
        f"WHERE {pending_filter_clause('node')}) "
        f"MERGE (alias:{MERGE_ALIAS_LABEL} {{merge_key: row.merge_key}}) "
        "ON CREATE SET alias.entity_id = row.id "
        f"WITH c, row, alias, candidate_edges WHERE {pending_filter_clause('alias')} "
        f"OPTIONAL MATCH (owner:{NODE_IDENTITY_LABEL} {{id: alias.entity_id}}) "
        f"WITH c, row, alias, candidate_edges, owner "
        "WHERE alias.entity_id = row.id OR "
        f"(owner IS NOT NULL AND {pending_filter_clause('owner')}) "
        "FOREACH (edge IN CASE WHEN alias.entity_id = row.id "
        "THEN candidate_edges ELSE [] END | DELETE edge) "
        "FOREACH (_ IN CASE WHEN alias.entity_id = row.id THEN [1] ELSE [] END | "
        f"REMOVE c:{CANDIDATE_LABEL} "
        f"SET c:{NODE_IDENTITY_LABEL}:{label_clause} "
        "SET c = {id: row.id, name: row.text, merge_key: row.merge_key, "
        "merge_count: row.count, source_chunk_ids: row.chunk_ids, "
        f"embedding: {embedding_value}, created_at: row.now}}) "
        "FOREACH (_ IN CASE WHEN alias.entity_id <> row.id AND owner IS NOT NULL "
        "THEN [1] ELSE [] END | SET owner.merge_count = "
        "coalesce(owner.merge_count, 1) + row.count, "
        "owner.source_chunk_ids = coalesce(owner.source_chunk_ids, []) + "
        "[chunk IN row.chunk_ids WHERE NOT chunk IN "
        "coalesce(owner.source_chunk_ids, [])]) "
        "RETURN row.id AS id, alias.entity_id AS owner_id, "
        "alias.entity_id = row.id AS converted"
    )


def fold_entity_candidates_query() -> str:
    """Fold an approved entity candidate into an existing owner."""
    return (
        f"UNWIND $rows AS row MATCH (c:{CANDIDATE_LABEL} "
        "{id: row.id, kind: 'entity', state: 'approved'}) "
        f"WHERE {pending_filter_clause('c')} "
        f"MATCH (owner:{NODE_IDENTITY_LABEL} {{id: row.owner_id}}) "
        f"WHERE {pending_filter_clause('owner')} "
        f"MATCH (chunk:{NODE_IDENTITY_LABEL}) WHERE chunk.id IN row.chunk_ids "
        f"AND {pending_filter_clause('chunk')} "
        "WITH c, owner, row, collect(DISTINCT chunk.id) AS chunk_ids "
        "WHERE size(chunk_ids) = size(row.chunk_ids) "
        "SET owner.merge_count = coalesce(owner.merge_count, 1) + row.count, "
        "owner.source_chunk_ids = coalesce(owner.source_chunk_ids, []) "
        "+ [chunk IN row.chunk_ids WHERE NOT chunk IN "
        "coalesce(owner.source_chunk_ids, [])] RETURN c.id AS id"
    )


def delete_evidence_edges_query() -> str:
    """Remove candidate evidence edges after entity conversion."""
    return (
        f"UNWIND $ids AS id MATCH (n:{NODE_IDENTITY_LABEL} {{id: id}})"
        f"-[edge:{EVIDENCED_BY}]->(chunk:{NODE_IDENTITY_LABEL}) "
        f"WHERE {pending_filter_clause('n')} AND {pending_filter_clause('edge')} "
        f"AND {pending_filter_clause('chunk')} DELETE edge RETURN id"
    )


def upsert_candidate_relations_query(rel_type: str) -> str:
    """Write approved relation candidates, returning only written candidate ids."""
    rel_type = validate_identifier(rel_type)
    return (
        f"UNWIND $records AS record MATCH (c:{CANDIDATE_LABEL} "
        "{id: record.candidate_id, kind: 'relation', state: 'approved'}) "
        f"WHERE {pending_filter_clause('c')} "
        f"MATCH (source:{NODE_IDENTITY_LABEL} {{id: record.start_id}}), "
        f"(target:{NODE_IDENTITY_LABEL} {{id: record.end_id}}) "
        f"WHERE {pending_filter_clause('source')} "
        f"AND {pending_filter_clause('target')} "
        f"MATCH (chunk:{NODE_IDENTITY_LABEL}) WHERE chunk.id IN record.chunk_ids "
        f"AND {pending_filter_clause('chunk')} "
        "WITH c, source, target, record, collect(DISTINCT chunk.id) AS chunk_ids "
        "WHERE size(chunk_ids) = size(record.chunk_ids) "
        f"MERGE (source)-[edge:{rel_type} {{id: record.id}}]->(target) "
        f"WITH c, edge, record WHERE {pending_filter_clause('edge')} "
        "SET edge.source_chunk_ids = coalesce(edge.source_chunk_ids, []) "
        "+ [chunk IN record.chunk_ids WHERE NOT chunk IN "
        "coalesce(edge.source_chunk_ids, [])], "
        "edge.created_at = coalesce(edge.created_at, record.now) "
        "RETURN c.id AS candidate_id, "
        "edge.id AS id"
    )


def set_candidate_property_query(property_name: str) -> str:
    """Set a typed candidate value on its owner and return handled ids."""
    property_name = validate_identifier(property_name)
    return (
        f"UNWIND $rows AS row MATCH (c:{CANDIDATE_LABEL} "
        "{id: row.candidate_id, kind: 'property', state: 'approved'}) "
        f"WHERE {pending_filter_clause('c')} "
        f"MATCH (entity:{NODE_IDENTITY_LABEL} {{id: row.entity_id}}) "
        f"WHERE {pending_filter_clause('entity')} "
        f"MATCH (chunk:{NODE_IDENTITY_LABEL}) WHERE chunk.id IN row.chunk_ids "
        f"AND {pending_filter_clause('chunk')} "
        "WITH c, entity, row, collect(DISTINCT chunk.id) AS chunk_ids "
        "WHERE size(chunk_ids) = size(row.chunk_ids) "
        f"SET entity.{property_name} = row.value, "
        "entity.source_chunk_ids = coalesce(entity.source_chunk_ids, []) + "
        "[chunk IN row.chunk_ids WHERE NOT chunk IN "
        "coalesce(entity.source_chunk_ids, [])] "
        "RETURN c.id AS candidate_id, entity.id AS id"
    )


def delete_candidates_query() -> str:
    """Delete only the approved candidate nodes returned as handled."""
    return (
        f"UNWIND $ids AS id MATCH (c:{CANDIDATE_LABEL} "
        "{id: id, state: 'approved'}) "
        f"WHERE {pending_filter_clause('c')} DETACH DELETE c RETURN id"
    )
