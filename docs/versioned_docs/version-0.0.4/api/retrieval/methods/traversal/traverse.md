---
title: agrag.retrieval.methods.traversal.traverse
sidebar_label: traverse
---

# `agrag.retrieval.methods.traversal.traverse` \{#agrag-retrieval-methods-traversal-traverse}

```python
traverse(seed:SearchResult, *, graph_store:GraphStore, settings:RetrievalSettings, relation_type:str | None = None, direction:TraversalDirection = 'both', depth:int = 1, limit:int = 10, community_expand:bool = False, community_top_k:int = 3, filters:SearchFilters | None = None, tracer:Tracer | None = None) -> list[SearchResult]
```

Expand one resolved entity into its neighbours.

**Parameters:**

- **seed** (<code>[SearchResult](../../../common/data_models/search_result/SearchResult.md)</code>) – The resolved entity to expand from. A ResolvedEntity seed
  expands from its raw member ids, never its own id.
- **graph_store** (<code>[GraphStore](../../../graphdb/base/GraphStore.md)</code>) – The graph to traverse.
- **settings** (<code>[RetrievalSettings](../../settings/RetrievalSettings.md)</code>) – Retrieval configuration, carrying the BFS defaults
  this call's explicit arguments override.
- **relation_type** (<code>str | None</code>) – Restrict the traversal to this single
  relationship type. None crosses every type the scope
  allows.
- **direction** (<code>TraversalDirection</code>) – Which way a hop walks each relationship, relative to
  the seed entity.
- **depth** (<code>int</code>) – Maximum hops. Clamped by the query builder.
- **limit** (<code>int</code>) – Maximum neighbours returned.
- **community_expand** (<code>bool</code>) – Also fuse in the reports of communities
  overlapping the seed, ranked by membership overlap.
- **community_top_k** (<code>int</code>) – Maximum community reports to add when
  `community_expand` is set.
- **filters** (<code>[SearchFilters](../../filters/SearchFilters.md) | None</code>) – Scope for the traversal. `relation_types` here is an
  immutable allowlist the caller set, not something a
  `relation_type` argument can widen: a request outside it
  is refused without querying the graph. `properties`
  `document_ids`, and `labels` constrain returned
  neighbour nodes.
- **tracer** (<code>Tracer | None</code>) – Opens the root span and flows to the BFS retriever and
  community expansion. None opens no recorded span.

**Returns:**

- <code>list\[[SearchResult](../../../common/data_models/search_result/SearchResult.md)\]</code> – The neighbouring entities, deduplicated, highest-ranked first,
- <code>list\[[SearchResult](../../../common/data_models/search_result/SearchResult.md)\]</code> – with any requested community reports fused in.

**Raises:**

- <code>[ScopeDeniedError](../../errors/ScopeDeniedError.md)</code> – relation_type names a type the caller's scope
  does not permit.
