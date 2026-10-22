"""Cypher builders for guarded vector synchronization and repair."""

from agrag.common.data_models.candidate import CANDIDATE_LABEL
from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.community import COMMUNITY_LABEL
from agrag.common.data_models.cutover_job import CUTOVER_JOB_LABEL
from agrag.common.data_models.document import DOCUMENT_LABEL
from agrag.common.data_models.resolved_entity import RESOLVED_ENTITY_LABEL
from agrag.common.data_models.structure import (
    DOCUMENT_ACTIVATION_LABEL,
    FIGURE_LABEL,
    SECTION_LABEL,
    SOURCE_LABEL,
    TABLE_LABEL,
)
from agrag.common.data_models.vector_record import VectorKind
from agrag.cypher.entities import NODE_IDENTITY_LABEL


_SYSTEM_LABELS = (
    CHUNK_LABEL,
    COMMUNITY_LABEL,
    RESOLVED_ENTITY_LABEL,
    DOCUMENT_LABEL,
    DOCUMENT_ACTIVATION_LABEL,
    SECTION_LABEL,
    TABLE_LABEL,
    FIGURE_LABEL,
    SOURCE_LABEL,
    CANDIDATE_LABEL,
    CUTOVER_JOB_LABEL,
    "VectorPlacement",
)


def vector_target_check_query(kind: VectorKind) -> str:
    """Build a read-only check for row ownership and embedding text guards.

    Returns only matching nodes whose guarded text still matches. A running
    job can distinguish its own rows from committed rows in the result.
    """
    label = {
        VectorKind.CHUNK: CHUNK_LABEL,
        VectorKind.ENTITY: "",
        VectorKind.RESOLVED_ENTITY: RESOLVED_ENTITY_LABEL,
        VectorKind.COMMUNITY: COMMUNITY_LABEL,
    }[kind]
    match_label = f":{label}" if label else ""
    guard = {
        VectorKind.CHUNK: "target.text = row.expected_text",
        VectorKind.ENTITY: (
            "target.name = row.expected_name AND "
            "coalesce(target.description, '') = row.expected_description"
        ),
        VectorKind.RESOLVED_ENTITY: (
            "target.name = row.expected_name AND "
            "coalesce(target.description, '') = row.expected_description"
        ),
        VectorKind.COMMUNITY: (
            "target.title = row.expected_title AND "
            "target.summary = row.expected_summary"
        ),
    }[kind]
    return (
        "UNWIND $rows AS row "
        f"MATCH (target:{NODE_IDENTITY_LABEL}{match_label} {{id: row.id}}) "
        "WHERE "
        "(row.pending_job_id IS NULL AND target._pending_job_id IS NULL) OR "
        "(row.pending_job_id IS NOT NULL AND "
        "(target._pending_job_id = row.pending_job_id OR "
        "target._pending_job_id IS NULL)) "
        "WITH target, row WHERE "
        "(row.pending_job_id IS NOT NULL AND target._pending_job_id IS NULL) "
        f"OR ({guard}) "
        "RETURN target.id AS id, "
        "CASE WHEN target._pending_job_id IS NULL "
        "AND row.pending_job_id IS NOT NULL THEN 'committed' "
        "ELSE 'owned' END AS state, "
        "[label IN labels(target) WHERE NOT label STARTS WITH '_'] AS labels"
    )


def node_labels_query() -> str:
    """Build a query returning searchable labels for nodes by id."""
    return (
        "UNWIND $ids AS id "
        f"MATCH (node:{NODE_IDENTITY_LABEL} {{id: id}}) "
        "WHERE node._pending_job_id IS NULL "
        "RETURN node.id AS id, "
        "[label IN labels(node) WHERE NOT label STARTS WITH '_'] AS labels"
    )


def community_ids_query() -> str:
    """Build a query returning every community id before a full replacement."""
    return f"MATCH (node:{NODE_IDENTITY_LABEL}:{COMMUNITY_LABEL}) RETURN node.id AS id"


def existing_ids_query(kind: VectorKind) -> str:
    """Build a query returning candidate ids that still exist as this kind."""
    label = {
        VectorKind.CHUNK: CHUNK_LABEL,
        VectorKind.ENTITY: "",
        VectorKind.RESOLVED_ENTITY: RESOLVED_ENTITY_LABEL,
        VectorKind.COMMUNITY: COMMUNITY_LABEL,
    }[kind]
    match_label = f":{label}" if label else ""
    exclusions = " AND ".join(f"NOT node:{name}" for name in _SYSTEM_LABELS)
    kind_filter = f" AND {exclusions}" if kind is VectorKind.ENTITY else ""
    return (
        "UNWIND $ids AS id "
        f"MATCH (node:{NODE_IDENTITY_LABEL}{match_label} {{id: id}}) "
        f"WHERE true{kind_filter} RETURN DISTINCT node.id AS id"
    )


def committed_vector_ids_query(kind: VectorKind) -> str:
    """Build a keyset page of committed nodes that need vector records."""
    label = {
        VectorKind.CHUNK: CHUNK_LABEL,
        VectorKind.ENTITY: "",
        VectorKind.RESOLVED_ENTITY: RESOLVED_ENTITY_LABEL,
        VectorKind.COMMUNITY: COMMUNITY_LABEL,
    }[kind]
    match_label = f":{label}" if label else ""
    exclusions = " AND ".join(f"NOT node:{name}" for name in _SYSTEM_LABELS)
    kind_filter = f" AND {exclusions}" if kind is VectorKind.ENTITY else ""
    return (
        f"MATCH (node:{NODE_IDENTITY_LABEL}{match_label}) "
        "WHERE node._pending_job_id IS NULL "
        "AND ($after IS NULL OR node.id > $after)"
        f"{kind_filter} "
        "RETURN node.id AS id ORDER BY node.id LIMIT $limit"
    )
