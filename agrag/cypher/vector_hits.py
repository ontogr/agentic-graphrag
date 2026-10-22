"""Cypher builders that join external vector hits to visible graph nodes."""

from typing import Any

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.document import DOCUMENT_LABEL
from agrag.common.data_models.structure import HAS_PART
from agrag.common.data_models.vector_record import VectorKind
from agrag.cypher._pending_filter import pending_filter_clause
from agrag.cypher.entities import NODE_IDENTITY_LABEL, filter_clause


def external_hits_query(
    filters: dict[str, Any] | None = None,
    *,
    kind: VectorKind,
) -> tuple[str, dict[str, Any]]:
    """Build the graph join for external vector results and property filters.

    Args:
        filters: Optional node-property filters in the same shape accepted by
            ``SearchFilters.to_property_filter``.
        kind: External collection type. Chunk hits must have an open
            ``HAS_PART`` edge before they count as graph hits.

    Returns:
        A query and its filter parameters. The caller supplies ``$rows``, whose
        entries contain ``id``, ``score`` and ``rank``.
    """
    chunk_label = f":{CHUNK_LABEL}" if kind is VectorKind.CHUNK else ""
    query = (
        "UNWIND $rows AS row "
        f"MATCH (node:{NODE_IDENTITY_LABEL}{chunk_label} {{id: row.id}}) "
        f"WHERE {pending_filter_clause('node')} "
    )
    where, parameters = filter_clause(filters or {})
    if where:
        query += f"AND {where.removeprefix('WHERE ')} "
    if kind is VectorKind.CHUNK:
        query += (
            f"MATCH (document:{NODE_IDENTITY_LABEL}:{DOCUMENT_LABEL})"
            f"-[part:{HAS_PART}]->(node) "
            f"WHERE part.invalid_at IS NULL AND {pending_filter_clause('part')} "
            "WITH DISTINCT node, row "
        )
    query += (
        "RETURN node.id AS id, row.score AS score, row.rank AS rank ORDER BY row.rank"
    )
    return query, parameters
