---
title: agrag.retrieval.search_engine.SearchEngine
sidebar_label: SearchEngine
---

# `agrag.retrieval.search_engine.SearchEngine` \{#agrag-retrieval-search_engine-SearchEngine}

```python
SearchEngine(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None, entity_labels:Sequence[str] | None = None, graph_schema:GraphSchema | None = None, tracer:Tracer | None = None) -> None
```

Retrieval's public entry point, independent of Graph.

Fans a query out to every method a Recipe names, fuses the
results, and optionally reranks them. Constructed from its own
stores. It does not depend on a Graph instance existing.

A `tracer` opens the retrieval spans and flows to every
retriever and free function the engine calls. It is not pushed
into `graph_store`, `embedder` or `vector_store`. Pass the
same tracer to those when you build them, so their adapter spans
nest under these retrieval spans.

**Functions:**

- [**find_entity**](#agrag-retrieval-search_engine-SearchEngine-find_entity) – Resolve a named entity to its top search hit, or None.
- [**list_relationship_types**](#agrag-retrieval-search_engine-SearchEngine-list_relationship_types) – List the relationship types directly attached to an entity.
- [**search**](#agrag-retrieval-search_engine-SearchEngine-search) – Run recipe's methods, fuse, expand, and optionally rerank.
- [**traverse**](#agrag-retrieval-search_engine-SearchEngine-traverse) – Expand one resolved entity into its neighbours.

**Attributes:**

- [**graph_schema**](#agrag-retrieval-search_engine-SearchEngine-graph_schema) (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – The schema retrieval is grounded in, GENERIC when none was given.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Always required. It backs entity and chunk search
  when vector_store is absent, and it always backs BFS.
- **embedder** (<code>[Embedder](../../embedding/base/Embedder.md)</code>) – Produces query vectors for dense and hybrid
  search.
- **vector_store** (<code>[VectorStore](../../vectordb/base/VectorStore.md) | None</code>) – Optional. When set, entity, chunk, and
  community search run hybrid_search there instead of
  GraphStore's native search. `Graph.open(vector_store=...)`
  provisions the collections and dual-writes every embedding
  this package ingests, so the two paths see the same data.
  Point it at a store that `Graph.open` provisioned: a
  missing collection makes each method that reads it fail, and
  `search` raises `AllRetrievalMethodsFailedError` when
  every method fails. Collections that exist but hold no
  records return no hits.
- **settings** (<code>[RetrievalSettings](../settings/RetrievalSettings.md) | None</code>) – Retrieval configuration; defaults from
  environment.
- **entity_labels** (<code>Sequence\[str\] | None</code>) – The entity labels native entity search runs
  against, one vector index each, as provisioned by
  `Graph.open`. Retained as a checked input only: it must
  name exactly the labels graph_schema declares, since the
  schema is what native search and generated Cypher both
  read. Omit it and let the schema drive both. Ignored when
  a vector_store is configured.
- **graph_schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md) | None</code>) – The graph's declared schema, ground truth for
  native entity labels and for generated Cypher. None uses
  `GENERIC`.
- **tracer** (<code>Tracer | None</code>) – Opens the search span and flows to every retriever
  and free function the engine calls. None opens no
  recorded span.

**Raises:**

- <code>ValueError</code> – entity_labels does not name exactly the labels
  graph_schema declares.

## `find_entity` \{#agrag-retrieval-search_engine-SearchEngine-find_entity}

```python
find_entity(name:str, *, filters:SearchFilters | None = None) -> SearchResult | None
```

Resolve a named entity to its top search hit, or None.

Searches this engine's configured entity_labels by default. A
filters.labels value, when set, overrides which labels are
searched rather than narrowing within entity_labels. This is the
same EntityRetriever behavior that the entity search of
search() already relies on.

**Parameters:**

- **name** (<code>str</code>) – The entity name (or description) to resolve.
- **filters** (<code>[SearchFilters](../filters/SearchFilters.md) | None</code>) – Scope to resolve within. An entity that exists
  only outside it resolves to None, the same as one that
  does not exist.

**Returns:**

- <code>[SearchResult](../../common/data_models/search_result/SearchResult.md) | None</code> – The top-ranked SearchResult, or None when nothing matched.

## `graph_schema` \{#agrag-retrieval-search_engine-SearchEngine-graph_schema}

```python
graph_schema: GraphSchema
```

The schema retrieval is grounded in, GENERIC when none was given.

## `list_relationship_types` \{#agrag-retrieval-search_engine-SearchEngine-list_relationship_types}

```python
list_relationship_types(seed:SearchResult, *, relation_type_filter:str | None = None, direction:TraversalDirection = 'both', filters:SearchFilters | None = None) -> list[str]
```

List the relationship types directly attached to an entity.

Depth-1 only: it reports what is attached to the seed, never
what lies past it.

**Parameters:**

- **seed** (<code>[SearchResult](../../common/data_models/search_result/SearchResult.md)</code>) – The resolved entity to read attached types from,
  normally from `find_entity`.
- **relation_type_filter** (<code>str | None</code>) – Only report this type, if present.
- **direction** (<code>TraversalDirection</code>) – Which way to inspect relationships, relative to the
  seed entity.
- **filters** (<code>[SearchFilters](../filters/SearchFilters.md) | None</code>) – Scope that limits visible relationship types.

**Returns:**

- <code>list\[str\]</code> – The distinct attached relationship type names.

## `search` \{#agrag-retrieval-search_engine-SearchEngine-search}

```python
search(query:str, recipe:Recipe, *, filters:SearchFilters | None = None) -> list[SearchResult]
```

Run recipe's methods, fuse, expand, and optionally rerank.

Runs recipe.methods concurrently and fuses their output
first. When recipe.bfs is set, BFS runs as a second,
sequential step seeded from the fused entity results. BFS
results are fused into the same list a second time before
reranking.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text.
- **recipe** (<code>[Recipe](../recipes/Recipe.md)</code>) – Which methods to run, whether to expand via BFS
  afterward, and which reranker, if any, follows.
- **filters** (<code>[SearchFilters](../filters/SearchFilters.md) | None</code>) – Constraints applied identically to every method.

**Returns:**

- <code>list\[[SearchResult](../../common/data_models/search_result/SearchResult.md)\]</code> – Up to recipe.limit results, ranked highest-relevance
  first.

**Raises:**

- <code>[AllRetrievalMethodsFailedError](../errors/AllRetrievalMethodsFailedError.md)</code> – Every method the recipe
  names failed. A method failing while others succeed
  is logged and its results are absent.
- <code>[UnknownRecipeMethodError](../errors/UnknownRecipeMethodError.md)</code> – The recipe names one or more
  methods that are not in the retriever registry. A
  misspelled method name is a configuration error. It
  is reported instead of silently returning no
  results.

## `traverse` \{#agrag-retrieval-search_engine-SearchEngine-traverse}

```python
traverse(seed:SearchResult, *, relation_type:str | None = None, direction:TraversalDirection = 'both', depth:int = 1, limit:int = 10, community_expand:bool = False, community_top_k:int = 3, filters:SearchFilters | None = None) -> list[SearchResult]
```

Expand one resolved entity into its neighbours.

**Parameters:**

- **seed** (<code>[SearchResult](../../common/data_models/search_result/SearchResult.md)</code>) – The resolved entity to expand from, normally from
  `find_entity`.
- **relation_type** (<code>str | None</code>) – Restrict the traversal to this one
  relationship type.
- **direction** (<code>TraversalDirection</code>) – Which way a hop walks each relationship,
  relative to the seed entity.
- **depth** (<code>int</code>) – Maximum hops.
- **limit** (<code>int</code>) – Maximum neighbours returned.
- **community_expand** (<code>bool</code>) – Also fuse in the reports of communities
  overlapping the seed.
- **community_top_k** (<code>int</code>) – Maximum community reports to add when
  `community_expand` is set.
- **filters** (<code>[SearchFilters](../filters/SearchFilters.md) | None</code>) – Scope for the traversal. Its `relation_types` is
  an allowlist. A `relation_type` argument cannot widen it.
  Its `properties`, `document_ids`, and `labels`
  constrain returned neighbour nodes.

**Returns:**

- <code>list\[[SearchResult](../../common/data_models/search_result/SearchResult.md)\]</code> – The neighbouring entities, deduplicated, highest-ranked
  first, with any requested community reports fused in.

**Raises:**

- <code>[ScopeDeniedError](../errors/ScopeDeniedError.md)</code> – relation_type names a type the caller's
  scope does not permit.
