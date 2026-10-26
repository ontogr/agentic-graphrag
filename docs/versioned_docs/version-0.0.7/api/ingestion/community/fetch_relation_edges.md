---
title: agrag.ingestion.community.fetch_relation_edges
sidebar_label: fetch_relation_edges
---

# `agrag.ingestion.community.fetch_relation_edges` \{#agrag-ingestion-community-fetch_relation_edges}

```python
fetch_relation_edges(graph_store:GraphStore, *, schema:GraphSchema, page_size:int = 5000) -> list[WeightedEdge]
```

Return current-schema entity relations as weighted edge tuples.

Weight is len(source_chunk_ids) (attestation count). A relation with
no attested chunks contributes weight 0.0, so an unsupported edge
cannot inflate clustering or a community report importance. Two
entities connected by more than one distinct relation type contribute
one edge tuple per type. graspologic_native sums parallel-edge
weights when it builds its own adjacency.

Pages by keyset on `(a.id, b.id, type(r), r.id)`.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where the relations are read from.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – The active entity and relation types for this graph.
- **page_size** (<code>int</code>) – Rows fetched per page.

**Returns:**

- <code>list\[[WeightedEdge](WeightedEdge.md)\]</code> – Edge tuples as (source_id_str, target_id_str, weight, rel_type).
