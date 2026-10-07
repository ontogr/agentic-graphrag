---
title: agrag.retrieval.rerank.node_distance.node_distance_rerank
sidebar_label: node_distance_rerank
---

# `agrag.retrieval.rerank.node_distance.node_distance_rerank` \{#agrag-retrieval-rerank-node_distance-node_distance_rerank}

```python
node_distance_rerank(results:list[SearchResult], *, graph_store:GraphStore, seed_ids:list[UUID], tracer:Tracer | None = None) -> list[SearchResult]
```

Rerank results by graph proximity to seed entity ids.

Uses shortest-path distance from each result entity to the
closest seed entity. Entities closer to seeds rank higher. A
ResolvedEntity item is measured by its closest raw member.
Results without an entity item (chunks, relations) are placed
at the end with a high distance penalty.

**Parameters:**

- **results** (<code>list\[[SearchResult](../../../common/data_models/search_result/SearchResult.md)\]</code>) – The fused results to rerank.
- **graph_store** (<code>[GraphStore](../../../graphdb/base/GraphStore.md)</code>) – The graph store for shortest-path queries.
- **seed_ids** (<code>list\[UUID\]</code>) – The seed entity ids to measure distance from. Seeds
  are the query's direct hits, not the whole candidate list:
  a candidate that is its own seed measures distance zero,
  so seeding with every candidate leaves the order unchanged.
- **tracer** (<code>Tracer | None</code>) – Opens the rerank span. None opens no recorded span.

**Returns:**

- <code>list\[[SearchResult](../../../common/data_models/search_result/SearchResult.md)\]</code> – Results reranked by proximity, closest first.

**Raises:**

- <code>Exception</code> – Any error the graph store raises. A candidate with no
  path to a seed is not an error and ranks with the penalty.
