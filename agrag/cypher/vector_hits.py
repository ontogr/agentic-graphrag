"""Cypher builders that join external vector hits to visible graph nodes."""

from typing import Any

from agrag.cypher._pending_filter import pending_filter_clause
from agrag.cypher.entities import NODE_IDENTITY_LABEL, filter_clause


def external_hits_query(
    filters: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Build the graph join for external vector results and property filters.

    Args:
        filters: Optional node-property filters in the same shape accepted by
            ``SearchFilters.to_property_filter``.

    Returns:
        A query and its filter parameters. The caller supplies ``$rows``, whose
        entries contain ``id``, ``score`` and ``rank``.
    """
    query = (
        "UNWIND $rows AS row "
        f"MATCH (node:{NODE_IDENTITY_LABEL} {{id: row.id}}) "
        f"WHERE {pending_filter_clause('node')} "
    )
    where, parameters = filter_clause(filters or {})
    if where:
        query += f"AND {where.removeprefix('WHERE ')} "
    query += (
        "RETURN node.id AS id, row.score AS score, row.rank AS rank "
        "ORDER BY row.rank"
    )
    return query, parameters
