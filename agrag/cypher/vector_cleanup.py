"""Cypher builders for external-vector cleanup during Cutover Jobs."""

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.community import COMMUNITY_LABEL
from agrag.common.data_models.graph_schema import RESERVED_ENTITY_LABELS
from agrag.common.data_models.resolved_entity import RESOLVED_ENTITY_LABEL
from agrag.cypher.entities import NODE_IDENTITY_LABEL


def document_chunk_ids_query() -> str:
    """Build a query returning every chunk id owned by a document."""
    return (
        f"MATCH (chunk:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} "
        "{document_id: $document_node_id}) "
        "RETURN chunk.id AS id"
    )


def pending_vector_ids_query() -> str:
    """Build a query returning vector-bearing node ids tagged by one job."""
    non_vector_labels = RESERVED_ENTITY_LABELS - {NODE_IDENTITY_LABEL}
    excluded = ", ".join(f"'{label}'" for label in sorted(non_vector_labels))
    return (
        f"MATCH (node:{NODE_IDENTITY_LABEL} {{_pending_job_id: $job_id}}) "
        "WITH node, CASE "
        f"WHEN node:{CHUNK_LABEL} THEN 'chunks' "
        f"WHEN node:{COMMUNITY_LABEL} THEN 'communities' "
        f"WHEN node:{RESOLVED_ENTITY_LABEL} THEN 'resolved_entities' "
        "ELSE 'entities' END AS kind "
        f"WHERE node:{CHUNK_LABEL} OR node:{COMMUNITY_LABEL} "
        f"OR node:{RESOLVED_ENTITY_LABEL} OR any(label IN labels(node) "
        f"WHERE NOT label IN [{excluded}]) "
        "RETURN node.id AS id, kind"
    )
