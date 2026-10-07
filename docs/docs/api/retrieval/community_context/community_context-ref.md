---
title: agrag.retrieval.community_context.community_context
sidebar_label: community_context
---

# `agrag.retrieval.community_context.community_context` \{#agrag-retrieval-community_context-community_context}

```python
community_context(entity_ids:list[UUID], *, graph_store:GraphStore, top_k:int = 3, filters:SearchFilters | None = None, tracer:Tracer | None = None) -> list[SearchResult]
```

Return the top-overlapping communities' reports for a set of entities.

Ranks candidate communities by how many of entity_ids are their
members (Microsoft GraphRAG's local-search pattern), then returns the
top_k as SearchResults so they flow through the same Fusion/Ledger
machinery as any other result.

**Parameters:**

- **entity_ids** (<code>list\[UUID\]</code>) – The entity ids already found by a search's other
  retrieval methods.
- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where the overlap lookup runs.
- **top_k** (<code>int</code>) – The maximum number of communities to return. Zero or
  negative returns no results without querying.
- **filters** (<code>[SearchFilters](../filters/SearchFilters.md) | None</code>) – Applied to the candidate community node via
  `document_ids`/`properties` (`to_cypher_where`); labels
  are not applied, since they check node labels and a Community
  node never carries an entity label. Community nodes carry no
  document or tenant scope of their own, so a filter naming a
  property Community nodes never have matches no communities --
  a document- or property-scoped search gets no community
  enrichment rather than one drawn from outside its scope.
- **tracer** (<code>Tracer | None</code>) – Opens the context span. None opens no recorded span.

**Returns:**

- <code>list\[[SearchResult](../../common/data_models/search_result/SearchResult.md)\]</code> – Up to top_k SearchResults wrapping Community items, highest overlap
- <code>list\[[SearchResult](../../common/data_models/search_result/SearchResult.md)\]</code> – first. Empty when entity_ids is empty or no community overlaps.
