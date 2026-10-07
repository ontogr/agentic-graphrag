---
title: agrag.retrieval.methods.vector.vector_search
sidebar_label: vector_search
---

# `agrag.retrieval.methods.vector.vector_search` \{#agrag-retrieval-methods-vector-vector_search}

```python
vector_search(query:str, *, embedder:Embedder, graph_store:GraphStore, vector_store:VectorStore | None, collection:str, labels:Sequence[str], limit:int, filters:SearchFilters | None, settings:RetrievalSettings, query_vector:Sequence[float] | None = None, tracer:Tracer | None = None) -> list[VectorHit]
```

Embed query and search on whichever store is configured.

When vector_store is set, runs hybrid_search there (dense plus
BM25, blended by settings.hybrid_alpha) against `collection`.
When it is None, runs GraphStore's native vector_search once per
label in `labels` and merges the hits, ignoring hybrid_alpha
since that path is dense-only. One native vector index exists per
label, so a search over several labels is several searches.

Both paths exclude records an in-flight Cutover Job wrote: the
VectorStore path with a committed-only payload filter, the native
path inside the vector query itself. A caller can therefore never
receive an uncommitted job's node or vector.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text to embed.
- **embedder** (<code>[Embedder](../../../embedding/base/Embedder.md)</code>) – Produces the query's dense vector.
- **graph_store** (<code>[GraphStore](../../../graphdb/base/GraphStore.md)</code>) – The GraphStore-native fallback target.
- **vector_store** (<code>[VectorStore](../../../vectordb/base/VectorStore.md) | None</code>) – The optional VectorStore target; None selects
  the GraphStore-native path.
- **collection** (<code>str</code>) – The VectorStore collection name.
- **labels** (<code>Sequence\[str\]</code>) – The node labels to search on the GraphStore-native
  path, each backed by its own vector index.
- **limit** (<code>int</code>) – Maximum hits to return.
- **filters** (<code>[SearchFilters](../../filters/SearchFilters.md) | None</code>) – Constraints translated to whichever store is
  searched. Labels are a payload key on the VectorStore
  path and choose the searched indexes on the native path,
  so they are not sent as node property filters.
- **settings** (<code>[RetrievalSettings](../../settings/RetrievalSettings.md)</code>) – Supplies hybrid_alpha for the VectorStore path.
- **query_vector** (<code>Sequence\[float\] | None</code>) – Precomputed query embedding. None embeds `query`.
- **tracer** (<code>Tracer | None</code>) – Opens the search span. None opens no recorded span.

**Returns:**

- <code>list\[[VectorHit](../../../common/data_models/vector_record/VectorHit.md)\]</code> – Ranked VectorHits, from whichever store was searched.

**Raises:**

- <code>ValueError</code> – The native path was selected with no labels to
  search.
