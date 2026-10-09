---
title: agrag.retrieval.retrievers.bfs.BFSRetriever
sidebar_label: BFSRetriever
---

# `agrag.retrieval.retrievers.bfs.BFSRetriever` \{#agrag-retrieval-retrievers-bfs-BFSRetriever}

```python
BFSRetriever(*, graph_store:GraphStore, settings:RetrievalSettings | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Retriever](../base/Retriever.md)</code>

Graph traversal from seed entity ids.

Takes seed entity ids (from a prior EntityRetriever call, or
supplied directly), runs bfs_expand_query, and hydrates the
returned entities through resolve_entity and relations directly.
Degree-capped by RetrievalSettings.traversal_limit.

**Functions:**

- [**retrieve**](#agrag-retrieval-retrievers-bfs-BFSRetriever-retrieve) – Run BFS expansion from seed entity ids.

**Attributes:**

- [**name**](#agrag-retrieval-retrievers-bfs-BFSRetriever-name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](../../../graphdb/base/GraphStore.md)</code>) – The graph store to traverse.
- **settings** (<code>[RetrievalSettings](../../settings/RetrievalSettings.md) | None</code>) – Retrieval configuration; defaults from
  environment.
- **tracer** (<code>Tracer | None</code>) – Opens the retriever and its children's spans. None
  opens no recorded span.

## `name` \{#agrag-retrieval-retrievers-bfs-BFSRetriever-name}

```python
name = 'bfs'
```

## `retrieve` \{#agrag-retrieval-retrievers-bfs-BFSRetriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int | None = None, seed_ids:list[UUID] | None = None, depth:int | None = None, direction:TraversalDirection = 'both') -> list[SearchResult]
```

Run BFS expansion from seed entity ids.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text (unused for BFS,
  kept for interface consistency).
- **filters** (<code>[SearchFilters](../../filters/SearchFilters.md) | None</code>) – Constraints applied to traversal. relation_types
  restrict which relationships the traversal crosses;
  property filters, document_ids, and labels restrict
  returned neighbor nodes.
- **limit** (<code>int | None</code>) – Maximum results. None uses traversal_limit.
- **seed_ids** (<code>list\[UUID\] | None</code>) – The entity ids to expand from. If None, BFS
  returns empty.
- **depth** (<code>int | None</code>) – BFS hops. None uses
  RetrievalSettings.traversal_depth.
- **direction** (<code>TraversalDirection</code>) – Which way a hop walks each relationship,
  relative to the seed entity. Defaults to `"both"`.

**Returns:**

- <code>list\[[SearchResult](../../../common/data_models/search_result/SearchResult.md)\]</code> – SearchResults with entities and relations found via BFS.
