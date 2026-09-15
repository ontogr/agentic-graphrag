"""Community-report enrichment: local-search-style budget-capped context."""

from collections.abc import Mapping
from typing import Any, cast
from uuid import UUID

from agrag.common.data_models.community import Community
from agrag.common.data_models.search_result import SearchResult
from agrag.cypher.community import communities_for_entities_query
from agrag.graphdb.base import GraphStore


def _parse_community_node(node: object) -> Community | None:
    """Parse a GraphStore node row into a Community, or None on failure."""
    try:
        props: dict = {}
        node_id: object = None
        if isinstance(node, dict) and "properties" in node:
            props = dict(node.get("properties") or {})
            node_id = node.get("id") or props.get("id")
        elif isinstance(node, dict) and "id" in node:
            props = dict(node)
            node_id = props.get("id")
        else:
            if not hasattr(node, "keys"):
                return None
            props = dict(cast(Mapping[str, Any], node))
            node_id = props.get("id")
        if node_id is None:
            return None

        community = Community(
            id=UUID(str(node_id)),
            title=str(props.get("title", "")),
            summary=str(props.get("summary", "")),
            rating=float(props.get("rating", 0.0)),
            rating_explanation=str(props.get("rating_explanation", "")),
            findings=list(props.get("findings") or []),
            member_ids=[UUID(str(m)) for m in props.get("member_ids") or []],
            internal_weight=float(props.get("internal_weight", 0.0)),
        )
        embedding = props.get("embedding")
        if embedding is not None:
            community.embedding = list(embedding)
        return community
    except Exception:
        return None


async def community_context(
    entity_ids: list[UUID], *, graph_store: GraphStore, top_k: int = 3
) -> list[SearchResult]:
    """Return the top-overlapping communities' reports for a set of entities.

    Ranks candidate communities by how many of entity_ids are their
    members (Microsoft GraphRAG's local-search pattern), then returns the
    top_k as SearchResults so they flow through the same Fusion/Ledger
    machinery as any other result.

    Args:
        entity_ids: The entity ids already found by a search's other
            retrieval methods.
        graph_store: Where the overlap lookup runs.
        top_k: The maximum number of communities to return.

    Returns:
        Up to top_k SearchResults wrapping Community items, highest overlap
        first. Empty when entity_ids is empty or no community overlaps.
    """
    if not entity_ids:
        return []
    rows = await graph_store.execute_read(
        communities_for_entities_query(),
        {"entity_ids": [str(e) for e in entity_ids]},
    )
    results: list[SearchResult] = []
    for row in rows[:top_k]:
        community = _parse_community_node(row.get("c", row))
        if community is None:
            continue
        results.append(
            SearchResult(
                item=community, score=float(row["overlap"]), method="community"
            )
        )
    return results
