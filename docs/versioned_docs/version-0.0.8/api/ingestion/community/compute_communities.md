---
title: agrag.ingestion.community.compute_communities
sidebar_label: compute_communities
---

# `agrag.ingestion.community.compute_communities` \{#agrag-ingestion-community-compute_communities}

```python
compute_communities(edges:list[WeightedEdge], *, max_cluster_size:int = 10, resolution:float = 1.0, seed:int | None = 3735928559) -> list[Community]
```

Run hierarchical Leiden and return level-0 communities.

CPU-bound and synchronous. Callers on the event loop must run this with
asyncio.to_thread (see chunk_documents for the same pattern with
chunking). Only level 0 is kept. Higher levels are computed for
max_cluster_size capping but never persisted.

After clustering, one extra pass over the same edge list computes a
structural-importance signal, entirely from data already in memory.
No new dependency and no new query. graspologic exposes no general
centrality function (see the follow-up research this refinement is
based on).

- Each community internal_weight (total weight of edges where both
  endpoints are its members). It signals which communities get a
  real LLM report instead of a heuristic one.
- Each member local weight (weight of its own internal edges).
  It orders member_ids highest-first, so the most representative
  members lead the list for both a large qualifying community's
  token-budget-truncated LLM prompt and a heuristic report's
  few-name summary.

**Parameters:**

- **edges** (<code>list\[[WeightedEdge](WeightedEdge.md)\]</code>) – The weighted edge list from fetch_relation_edges, as
  (source_id, target_id, weight, relation_type) tuples.
- **max_cluster_size** (<code>int</code>) – The size ceiling a cluster is split past, at every
  level.
- **resolution** (<code>float</code>) – Leiden's resolution parameter.
- **seed** (<code>int | None</code>) – Random seed for reproducibility. None uses the native
  default.

**Returns:**

- <code>list\[[Community](../../common/data_models/community/Community-ref.md)\]</code> – One Community per level-0 cluster with two or more members, with
  member_ids ordered by local weight descending and internal_weight
  set. Reports (title, summary, rating, findings) are left empty.
  Report generation fills them.

**Raises:**

- <code>[CommunityDetectionMissingExtraError](CommunityDetectionMissingExtraError.md)</code> – graspologic-native is not
  installed.
