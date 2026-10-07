---
title: agrag.retrieval.methods.traversal.find_entity
sidebar_label: find_entity
---

# `agrag.retrieval.methods.traversal.find_entity` \{#agrag-retrieval-methods-traversal-find_entity}

```python
find_entity(name:str, *, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None, settings:RetrievalSettings, entity_labels:Sequence[str], filters:SearchFilters | None = None, tracer:Tracer | None = None) -> SearchResult | None
```

Resolve a named entity to its top search hit, or None.

Runs one entity search and returns its best result, which callers
keep whole rather than unwrapping: the item renders as evidence,
and the result itself is what `extract_entity_ids` can turn
into traversal seeds.

**Parameters:**

- **name** (<code>str</code>) – The entity name (or description) to resolve.
- **graph_store** (<code>[GraphStore](../../../graphdb/base/GraphStore.md)</code>) – Backs entity search when vector_store is absent.
- **embedder** (<code>[Embedder](../../../embedding/base/Embedder.md)</code>) – Produces the query vector.
- **vector_store** (<code>[VectorStore](../../../vectordb/base/VectorStore.md) | None</code>) – Optional vector store for hybrid search.
- **settings** (<code>[RetrievalSettings](../../settings/RetrievalSettings.md)</code>) – Retrieval configuration.
- **entity_labels** (<code>Sequence\[str\]</code>) – The labels native entity search runs against by
  default, one vector index each.
- **filters** (<code>[SearchFilters](../../filters/SearchFilters.md) | None</code>) – Scope to resolve within. Labels, document ids, and
  `properties` are projected through, matching the
  projection that a plain search's own entity step applies. A
  `filters.labels` value replaces `entity_labels` rather
  than narrowing within it, so a scope carrying only
  unrelated fields must not be mistaken for a deliberate
  label override. An entity that exists only outside this
  scope resolves to None, the same as one that does not
  exist.
- **tracer** (<code>Tracer | None</code>) – Opens the root span and flows to the entity retriever.
  None opens no recorded span.

**Returns:**

- <code>[SearchResult](../../../common/data_models/search_result/SearchResult.md) | None</code> – The top-ranked SearchResult, or None when nothing matched.
