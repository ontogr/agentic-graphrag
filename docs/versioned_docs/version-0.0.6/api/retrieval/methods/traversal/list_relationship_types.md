---
title: agrag.retrieval.methods.traversal.list_relationship_types
sidebar_label: list_relationship_types
---

# `agrag.retrieval.methods.traversal.list_relationship_types` \{#agrag-retrieval-methods-traversal-list_relationship_types}

```python
list_relationship_types(seed:SearchResult, *, graph_store:GraphStore, relation_type_filter:str | None = None, direction:TraversalDirection = 'both', filters:SearchFilters | None = None, tracer:Tracer | None = None) -> list[str]
```

List the relationship types directly attached to a resolved entity.

Depth-1 only: it reports what is attached to the seed, never what
lies past it. Any relation type allowlist in `filters` is applied
before the query runs.

**Parameters:**

- **seed** (<code>[SearchResult](../../../common/data_models/search_result/SearchResult.md)</code>) – The resolved entity to read attached types from.
- **graph_store** (<code>[GraphStore](../../../graphdb/base/GraphStore.md)</code>) – The graph to read.
- **relation_type_filter** (<code>str | None</code>) – Only report this type, if present.
- **direction** (<code>TraversalDirection</code>) – Which way to inspect relationships, relative to the seed.
- **filters** (<code>[SearchFilters](../../filters/SearchFilters.md) | None</code>) – Scope that limits which relationship types are visible.
- **tracer** (<code>Tracer | None</code>) – Opens the root span. None opens no recorded span.

**Returns:**

- <code>list\[str\]</code> – The distinct attached relationship type names.
