"""Node distance reranker: reorder by graph proximity to seeds."""

from uuid import UUID

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.search_result import SearchResult
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.graphdb.base import GraphStore


async def node_distance_rerank(
    results: list[SearchResult],
    *,
    graph_store: GraphStore,
    seed_ids: list[UUID],
) -> list[SearchResult]:
    """Rerank results by graph proximity to seed entity ids.

    Uses shortest-path distance from each result entity to the
    closest seed entity. Entities closer to seeds rank higher.
    Results without an entity item (chunks, relations) are placed
    at the end with a high distance penalty.

    Args:
        results: The fused results to rerank.
        graph_store: The graph store for shortest-path queries.
        seed_ids: The seed entity ids to measure distance from.

    Returns:
        Results reranked by proximity, closest first.
    """
    if not results or not seed_ids:
        return results

    seed_strs = [str(sid) for sid in seed_ids]

    scored: list[tuple[float, SearchResult]] = []
    for result in results:
        item = result.item
        if not isinstance(item, Entity):
            scored.append((999999.0, result))
            continue

        try:
            rows = await graph_store.execute_read(
                f"UNWIND $seed_ids AS seed_id "
                f"MATCH path = shortestPath("
                f"  (seed:{NODE_IDENTITY_LABEL} {{id: seed_id}})"
                f"-[*]-(target:{NODE_IDENTITY_LABEL} {{id: $target_id}})"
                f") "
                f"RETURN length(path) AS dist",
                {"seed_ids": seed_strs, "target_id": str(item.id)},
            )
            if rows and rows[0].get("dist") is not None:
                dist = float(rows[0]["dist"])
            else:
                dist = 999999.0
        except Exception:
            dist = 999999.0

        scored.append((dist, result))

    scored.sort(key=lambda pair: pair[0])
    return [result for _, result in scored]
