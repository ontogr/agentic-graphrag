"""Node distance reranker: reorder by graph proximity to seeds."""

from uuid import UUID

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.resolved_entity import ResolvedEntity
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
    closest seed entity. Entities closer to seeds rank higher. A
    ResolvedEntity item is measured by its closest raw member.
    Results without an entity item (chunks, relations) are placed
    at the end with a high distance penalty.

    Args:
        results: The fused results to rerank.
        graph_store: The graph store for shortest-path queries.
        seed_ids: The seed entity ids to measure distance from. Seeds
            are the query's direct hits, not the whole candidate list:
            a candidate that is its own seed measures distance zero,
            so seeding with every candidate leaves the order unchanged.

    Returns:
        Results reranked by proximity, closest first.
    """
    if not results or not seed_ids:
        return results

    seed_strs = [str(sid) for sid in seed_ids]

    scored: list[tuple[float, SearchResult]] = []
    for result in results:
        item = result.item
        if isinstance(item, Entity):
            target_ids = [item.id]
        elif isinstance(item, ResolvedEntity):
            target_ids = item.member_ids
        else:
            scored.append((999999.0, result))
            continue
        if not target_ids:
            scored.append((999999.0, result))
            continue

        try:
            rows = await graph_store.execute_read(
                f"UNWIND $seed_ids AS seed_id "
                f"UNWIND $target_ids AS target_id "
                f"MATCH path = shortestPath("
                f"  (seed:{NODE_IDENTITY_LABEL} {{id: seed_id}})"
                f"-[*]-(target:{NODE_IDENTITY_LABEL} {{id: target_id}})"
                f") "
                f"RETURN length(path) AS dist",
                {
                    "seed_ids": seed_strs,
                    "target_ids": [str(target_id) for target_id in target_ids],
                },
            )
            distances = [
                float(row["dist"]) for row in rows if row.get("dist") is not None
            ]
            dist = min(distances) if distances else 999999.0
        except Exception:
            dist = 999999.0

        scored.append((dist, result))

    scored.sort(key=lambda pair: pair[0])
    return [result for _, result in scored]
