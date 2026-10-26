---
title: agrag.retrieval.methods.vector.vector_search
sidebar_label: vector_search
---

# `agrag.retrieval.methods.vector.vector_search` \{#agrag-retrieval-methods-vector-vector_search}

```python
vector_search(query:str, *, embedder:Embedder, graph_store:GraphStore, labels:Sequence[str], limit:int, filters:SearchFilters | None, query_vector:Sequence[float] | None = None, vector_store:VectorStore | None = None, hybrid:bool = False, alpha:float = 0.5, tracer:Tracer | None = None) -> list[VectorHit]
```

Embed query and run GraphStore's native vector search for each label.

Native vector search uses one index per label. An external store groups
labels by vector kind and joins candidates back to committed graph nodes.

The vector query excludes records an in-flight Cutover Job wrote, so a
caller never receives an uncommitted job's node or vector.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text to embed.
- **embedder** (<code>[Embedder](../../../embedding/base/Embedder.md)</code>) – Produces the query's dense vector.
- **graph_store** (<code>[GraphStore](../../../graphdb/base/GraphStore.md)</code>) – Runs the native vector search.
- **labels** (<code>Sequence\[str\]</code>) – The node labels to search, each backed by its own vector index.
- **limit** (<code>int</code>) – Maximum hits to return.
- **filters** (<code>[SearchFilters](../../filters/SearchFilters.md) | None</code>) – Constraints applied as node property filters. Labels choose
  the searched indexes, so they are not sent as property filters.
- **query_vector** (<code>Sequence\[float\] | None</code>) – Precomputed query embedding. None embeds `query`.
- **vector_store** (<code>[VectorStore](../../../vectordb/base/VectorStore.md) | None</code>) – Optional external store for vector candidates.
- **hybrid** (<code>bool</code>) – Use the store's dense and lexical hybrid search when available.
- **alpha** (<code>float</code>) – Dense weight for external hybrid search.
- **tracer** (<code>Tracer | None</code>) – Opens the search span. None opens no recorded span.

**Returns:**

- <code>list\[[VectorHit](../../../common/data_models/vector_record/VectorHit.md)\]</code> – Ranked VectorHits.

**Raises:**

- <code>ValueError</code> – No labels were given to search.
