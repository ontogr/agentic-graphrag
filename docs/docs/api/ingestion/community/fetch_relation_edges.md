---
title: agrag.ingestion.community.fetch_relation_edges
sidebar_label: fetch_relation_edges
---

# `agrag.ingestion.community.fetch_relation_edges` \{#agrag-ingestion-community-fetch_relation_edges}

```python
fetch_relation_edges(graph_store:GraphStore, *, page_size:int = 5000, use_cursor:bool = True) -> list[WeightedEdge]
```

Return every live domain relation as a weighted edge tuple.

Weight is len(source_chunk_ids) (attestation count). A relation with
no attested chunks contributes weight 0.0, so an unsupported edge
cannot inflate clustering or a community report importance. Two
entities connected by more than one distinct relation type contribute
one edge tuple per type. graspologic_native sums parallel-edge
weights when it builds its own adjacency.

Supports cursor (keyset) pagination for large graphs where `SKIP`
is expensive, and legacy `SKIP` pagination for callers that need
it.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where the relations are read from.
- **page_size** (<code>int</code>) – Rows fetched per page.
- **use_cursor** (<code>bool</code>) – When True uses keyset pagination on `(a.id, b.id, type(r), r.id)`; when False uses `SKIP` pagination.

**Returns:**

- <code>list\[[WeightedEdge](WeightedEdge.md)\]</code> – Edge tuples as (source_id_str, target_id_str, weight, rel_type).
