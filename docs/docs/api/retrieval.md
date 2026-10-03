---
title: agrag.retrieval
sidebar_position: 11
---

## `agrag.retrieval` \{#agrag-retrieval}

Retrieval package: search engine, fusion, reranking, and retrievers.

**Modules:**

- [**community_context**](#agrag-retrieval-community_context) – Community-report enrichment: local-search-style budget-capped context.
- [**errors**](#agrag-retrieval-errors) – Errors that the retrieval layer raises.
- [**filters**](#agrag-retrieval-filters) – Constraints applied across every retrieval method in one call.
- [**fusion**](#agrag-retrieval-fusion) – Reciprocal Rank Fusion: combine ranked results from multiple methods.
- [**methods**](#agrag-retrieval-methods) – Low-level search method helpers shared by retrievers.
- [**recipes**](#agrag-retrieval-recipes) – Named, data-only configurations of what SearchEngine runs.
- [**rerank**](#agrag-retrieval-rerank) – Rerankers that reorder fused search results.
- [**resolved_entities**](#agrag-retrieval-resolved_entities) – Hydration helpers for resolved-entities.
- [**retrievers**](#agrag-retrieval-retrievers) – Retriever implementations for entity, chunk, BFS, and text2cypher search.
- [**search_engine**](#agrag-retrieval-search_engine) – Retrieval's public entry point, independent of Graph.
- [**settings**](#agrag-retrieval-settings) – Env-backed configuration for retrieval methods and fusion.
- [**tracing**](#agrag-retrieval-tracing) – Span helpers shared by the retrieval spans.

**Classes:**

- [**AllRetrievalMethodsFailedError**](#agrag-retrieval-AllRetrievalMethodsFailedError) – Every retrieval method a Recipe named failed.
- [**BFSRetriever**](#agrag-retrieval-BFSRetriever) – Graph traversal from seed entity ids.
- [**ChunkRetriever**](#agrag-retrieval-ChunkRetriever) – Dense chunk search via vector similarity.
- [**CommunityRetriever**](#agrag-retrieval-CommunityRetriever) – Dense search over community reports, for direct thematic questions.
- [**EntityRetriever**](#agrag-retrieval-EntityRetriever) – Dense entity search via vector similarity.
- [**Recipe**](#agrag-retrieval-Recipe) – A named configuration of what SearchEngine runs for a query.
- [**RetrievalError**](#agrag-retrieval-RetrievalError) – The base class for every retrieval error.
- [**RetrievalSettings**](#agrag-retrieval-RetrievalSettings) – Configuration for retrieval methods and fusion.
- [**Retriever**](#agrag-retrieval-Retriever) – One retrieval method: given a query, return SearchResults.
- [**ScopeDeniedError**](#agrag-retrieval-ScopeDeniedError) – A request asked for data outside the caller's permitted scope.
- [**SearchEngine**](#agrag-retrieval-SearchEngine) – Retrieval's public entry point, independent of Graph.
- [**SearchFilters**](#agrag-retrieval-SearchFilters) – Constraints applied across every retrieval method in one call.
- [**Text2CypherRetriever**](#agrag-retrieval-Text2CypherRetriever) – Let the agent ask structured questions via generated Cypher.
- [**UnknownRecipeMethodError**](#agrag-retrieval-UnknownRecipeMethodError) – A Recipe named a method SearchEngine does not know how to run.

**Attributes:**

- [**CHUNK**](#agrag-retrieval-CHUNK) –
- [**ENTITY**](#agrag-retrieval-ENTITY) –
- [**GRAPH_EXPAND**](#agrag-retrieval-GRAPH_EXPAND) –
- [**HYBRID**](#agrag-retrieval-HYBRID) –
- [**HYBRID_RERANKED**](#agrag-retrieval-HYBRID_RERANKED) –
- [**TEXT2CYPHER**](#agrag-retrieval-TEXT2CYPHER) –
- [**THEMATIC**](#agrag-retrieval-THEMATIC) –

### `agrag.retrieval.AllRetrievalMethodsFailedError` \{#agrag-retrieval-AllRetrievalMethodsFailedError}

```python
AllRetrievalMethodsFailedError(failures:dict[str, BaseException]) -> None
```

Bases: <code>[RetrievalError](#agrag-retrieval-errors-RetrievalError)</code>

Every retrieval method a Recipe named failed.

Raised instead of returning an empty result list so a total
retrieval outage is not mistaken for a query with no matches.

**Attributes:**

- [**failures**](#agrag-retrieval-AllRetrievalMethodsFailedError-failures) – Each failed method name mapped to the exception it
  raised.

#### `agrag.retrieval.AllRetrievalMethodsFailedError.failures` \{#agrag-retrieval-AllRetrievalMethodsFailedError-failures}

```python
failures = failures
```

### `agrag.retrieval.BFSRetriever` \{#agrag-retrieval-BFSRetriever}

```python
BFSRetriever(*, graph_store:GraphStore, settings:RetrievalSettings | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Retriever](#agrag-retrieval-retrievers-base-Retriever)</code>

Graph traversal from seed entity ids.

Takes seed entity ids (from a prior EntityRetriever call, or
supplied directly), runs bfs_expand_query, and hydrates the
returned entities and relations directly.
Degree-capped by RetrievalSettings.traversal_limit.

**Functions:**

- [**retrieve**](#agrag-retrieval-BFSRetriever-retrieve) – Run BFS expansion from seed entity ids.

**Attributes:**

- [**name**](#agrag-retrieval-BFSRetriever-name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – The graph store to traverse.
- **settings** (<code>[RetrievalSettings](#agrag-retrieval-settings-RetrievalSettings) | None</code>) – Retrieval configuration; defaults from
  environment.
- **tracer** (<code>Tracer | None</code>) – Opens the retriever and its children's spans. None
  opens no recorded span.

#### `agrag.retrieval.BFSRetriever.name` \{#agrag-retrieval-BFSRetriever-name}

```python
name = 'bfs'
```

#### `agrag.retrieval.BFSRetriever.retrieve` \{#agrag-retrieval-BFSRetriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int | None = None, seed_ids:list[UUID] | None = None, depth:int | None = None, direction:TraversalDirection = 'both') -> list[SearchResult]
```

Run BFS expansion from seed entity ids.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text (unused for BFS,
  kept for interface consistency).
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Constraints applied to traversal. relation_types
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

- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – SearchResults with entities and relations found via BFS.

### `agrag.retrieval.CHUNK` \{#agrag-retrieval-CHUNK}

```python
CHUNK = Recipe(methods=['chunk'], limit=10)
```

### `agrag.retrieval.ChunkRetriever` \{#agrag-retrieval-ChunkRetriever}

```python
ChunkRetriever(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Retriever](#agrag-retrieval-retrievers-base-Retriever)</code>

Dense chunk search via vector similarity.

Embeds the query, searches via the GraphStore-native or VectorStore
path, then hydrates each hit into a Chunk. The native
path searches the `Chunk` vector index ingestion provisions; the
VectorStore path searches `chunk_collection`.

**Functions:**

- [**retrieve**](#agrag-retrieval-ChunkRetriever-retrieve) – Run chunk search and return hydrated results.

**Attributes:**

- [**name**](#agrag-retrieval-ChunkRetriever-name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Backs chunk search when vector_store is
  absent.
- **embedder** (<code>[Embedder](embedding.md#agrag-embedding-base-Embedder)</code>) – Produces query vectors.
- **vector_store** (<code>[VectorStore](vectordb.md#agrag-vectordb-base-VectorStore) | None</code>) – Optional VectorStore for hybrid search.
- **settings** (<code>[RetrievalSettings](#agrag-retrieval-settings-RetrievalSettings) | None</code>) – Retrieval configuration; defaults from
  environment.
- **tracer** (<code>Tracer | None</code>) – Opens the retriever and its children's spans. None
  opens no recorded span.

#### `agrag.retrieval.ChunkRetriever.name` \{#agrag-retrieval-ChunkRetriever-name}

```python
name = 'chunk'
```

#### `agrag.retrieval.ChunkRetriever.retrieve` \{#agrag-retrieval-ChunkRetriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int | None = None) -> list[SearchResult]
```

Run chunk search and return hydrated results.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Constraints applied to the search.
- **limit** (<code>int | None</code>) – Maximum results. None uses settings.chunk_top_k.
  Zero or negative returns no results without searching.

**Returns:**

- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – Ranked SearchResults with hydrated Chunk items. A child chunk result
- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – carries its parent chunk in `SearchResult.parent`.

### `agrag.retrieval.CommunityRetriever` \{#agrag-retrieval-CommunityRetriever}

```python
CommunityRetriever(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Retriever](#agrag-retrieval-retrievers-base-Retriever)</code>

Dense search over community reports, for direct thematic questions.

**Functions:**

- [**retrieve**](#agrag-retrieval-CommunityRetriever-retrieve) – Run community-report search and return hydrated results.

**Attributes:**

- [**name**](#agrag-retrieval-CommunityRetriever-name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Where community nodes live.
- **embedder** (<code>[Embedder](embedding.md#agrag-embedding-base-Embedder)</code>) – Produces query vectors.
- **vector_store** (<code>[VectorStore](vectordb.md#agrag-vectordb-base-VectorStore) | None</code>) – Optional VectorStore for hybrid search.
- **settings** (<code>[RetrievalSettings](#agrag-retrieval-settings-RetrievalSettings) | None</code>) – Retrieval configuration; defaults from environment.
- **tracer** (<code>Tracer | None</code>) – Opens the retriever and its children's spans. None
  opens no recorded span.

#### `agrag.retrieval.CommunityRetriever.name` \{#agrag-retrieval-CommunityRetriever-name}

```python
name = 'community'
```

#### `agrag.retrieval.CommunityRetriever.retrieve` \{#agrag-retrieval-CommunityRetriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int | None = None) -> list[SearchResult]
```

Run community-report search and return hydrated results.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Constraints applied to the search.
- **limit** (<code>int | None</code>) – Maximum results. None uses settings.community_top_k.
  Zero or negative returns no results without searching.

### `agrag.retrieval.ENTITY` \{#agrag-retrieval-ENTITY}

```python
ENTITY = Recipe(methods=['entity'], limit=10)
```

### `agrag.retrieval.EntityRetriever` \{#agrag-retrieval-EntityRetriever}

```python
EntityRetriever(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None, entity_labels:Sequence[str] | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Retriever](#agrag-retrieval-retrievers-base-Retriever)</code>

Dense entity search via vector similarity.

Embeds the query, searches via the GraphStore-native or
VectorStore path, then hydrates every hit from the graph. A hit that
no longer exists in the graph is dropped.

The native path searches one vector index per entity label, so it
needs the labels ingestion provisioned indexes for: the label
filter when the caller sets one, otherwise `entity_labels`.

**Functions:**

- [**retrieve**](#agrag-retrieval-EntityRetriever-retrieve) – Run entity search and return hydrated results.

**Attributes:**

- [**name**](#agrag-retrieval-EntityRetriever-name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Backs entity search when vector_store is
  absent.
- **embedder** (<code>[Embedder](embedding.md#agrag-embedding-base-Embedder)</code>) – Produces query vectors.
- **vector_store** (<code>[VectorStore](vectordb.md#agrag-vectordb-base-VectorStore) | None</code>) – Optional VectorStore for hybrid search.
- **settings** (<code>[RetrievalSettings](#agrag-retrieval-settings-RetrievalSettings) | None</code>) – Retrieval configuration; defaults from
  environment.
- **entity_labels** (<code>Sequence\[str\] | None</code>) – The schema entity labels native search runs
  against. None uses settings.entity_labels.
- **tracer** (<code>Tracer | None</code>) – Opens the retriever and its children's spans. None
  opens no recorded span.

#### `agrag.retrieval.EntityRetriever.name` \{#agrag-retrieval-EntityRetriever-name}

```python
name = 'entity'
```

#### `agrag.retrieval.EntityRetriever.retrieve` \{#agrag-retrieval-EntityRetriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int | None = None) -> list[SearchResult]
```

Run entity search and return hydrated results.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Constraints applied to the search.
- **limit** (<code>int | None</code>) – Maximum results. None uses settings.entity_top_k.
  Zero or negative returns no results without searching.

**Returns:**

- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – Ranked SearchResults with resolved entity ids.

**Raises:**

- <code>ValueError</code> – Native search was selected and neither the
  filter nor the configuration names an entity label.

### `agrag.retrieval.GRAPH_EXPAND` \{#agrag-retrieval-GRAPH_EXPAND}

```python
GRAPH_EXPAND = Recipe(methods=['entity'], bfs=True, limit=20, community_expand=True)
```

### `agrag.retrieval.HYBRID` \{#agrag-retrieval-HYBRID}

```python
HYBRID = Recipe(methods=['entity', 'chunk'], limit=10)
```

### `agrag.retrieval.HYBRID_RERANKED` \{#agrag-retrieval-HYBRID_RERANKED}

```python
HYBRID_RERANKED = Recipe(methods=['entity', 'chunk'], reranker='cross_encoder', limit=10, community_expand=True)
```

### `agrag.retrieval.Recipe` \{#agrag-retrieval-Recipe}

Bases: <code>BaseModel</code>

A named configuration of what SearchEngine runs for a query.

**Attributes:**

- [**methods**](#agrag-retrieval-Recipe-methods) (<code>list\[str\]</code>) – Which retrieval methods to fan out to
  concurrently, by name.
- [**bfs**](#agrag-retrieval-Recipe-bfs) (<code>bool</code>) – Whether to run a BFS expansion after methods
  complete, seeded from their entity results. BFS
  needs seed ids methods produce, so it cannot run
  concurrently with them.
- [**bfs_depth**](#agrag-retrieval-Recipe-bfs_depth) (<code>int | None</code>) – Traversal depth when bfs is true. None uses
  RetrievalSettings.traversal_depth.
- [**reranker**](#agrag-retrieval-Recipe-reranker) (<code>Literal['cross_encoder', 'node_distance'] | None</code>) – The optional Rerank pass to run after Fusion.
  None skips reranking.
- [**min_score**](#agrag-retrieval-Recipe-min_score) (<code>float | None</code>) – Results the reranker scores below this are dropped.
  None uses RetrievalSettings.reranker_min_score, so a caller
  can tighten the floor for one call without touching the
  configured default.
- [**limit**](#agrag-retrieval-Recipe-limit) (<code>int</code>) – The maximum number of results SearchEngine
  returns.
- [**community_expand**](#agrag-retrieval-Recipe-community_expand) (<code>bool</code>) – Whether to fetch and fuse in overlapping
  communities' reports after BFS.
- [**community_top_k**](#agrag-retrieval-Recipe-community_top_k) (<code>int</code>) – How many communities community_context
  returns, and (when reranker is cross_encoder) how many
  are reserved a slot after rerank.

#### `agrag.retrieval.Recipe.bfs` \{#agrag-retrieval-Recipe-bfs}

```python
bfs: bool = False
```

#### `agrag.retrieval.Recipe.bfs_depth` \{#agrag-retrieval-Recipe-bfs_depth}

```python
bfs_depth: int | None = None
```

#### `agrag.retrieval.Recipe.community_expand` \{#agrag-retrieval-Recipe-community_expand}

```python
community_expand: bool = False
```

#### `agrag.retrieval.Recipe.community_top_k` \{#agrag-retrieval-Recipe-community_top_k}

```python
community_top_k: int = 3
```

#### `agrag.retrieval.Recipe.limit` \{#agrag-retrieval-Recipe-limit}

```python
limit: int = 10
```

#### `agrag.retrieval.Recipe.methods` \{#agrag-retrieval-Recipe-methods}

```python
methods: list[str]
```

#### `agrag.retrieval.Recipe.min_score` \{#agrag-retrieval-Recipe-min_score}

```python
min_score: float | None = None
```

#### `agrag.retrieval.Recipe.reranker` \{#agrag-retrieval-Recipe-reranker}

```python
reranker: Literal['cross_encoder', 'node_distance'] | None = None
```

### `agrag.retrieval.RetrievalError` \{#agrag-retrieval-RetrievalError}

Bases: <code>Exception</code>

The base class for every retrieval error.

### `agrag.retrieval.RetrievalSettings` \{#agrag-retrieval-RetrievalSettings}

Bases: <code>BaseSettings</code>

Configuration for retrieval methods and fusion.

**Attributes:**

- [**entity_collection**](#agrag-retrieval-RetrievalSettings-entity_collection) (<code>str</code>) – The VectorStore collection name for entity
  search. Only read when a VectorStore is configured on
  SearchEngine; ignored on the GraphStore-native path.
- [**resolved_entity_collection**](#agrag-retrieval-RetrievalSettings-resolved_entity_collection) (<code>str</code>) – The VectorStore collection name for
  resolved-entity search. Same condition as
  entity_collection.
- [**chunk_collection**](#agrag-retrieval-RetrievalSettings-chunk_collection) (<code>str</code>) – The VectorStore collection name for chunk
  search. Same condition as entity_collection.
- [**entity_labels**](#agrag-retrieval-RetrievalSettings-entity_labels) (<code>list\[str\]</code>) – The graph labels native entity search runs
  against, one vector index each. These are the schema's
  entity labels, never a VectorStore collection name. Only
  read when no VectorStore is configured and the caller
  passes no label filter.
- [**node_distance_seed_top_k**](#agrag-retrieval-RetrievalSettings-node_distance_seed_top_k) (<code>int</code>) – How many of the highest-ranked
  entity hits seed the node-distance reranker. Candidates
  are ordered by graph distance to those seeds.
- [**entity_top_k**](#agrag-retrieval-RetrievalSettings-entity_top_k) (<code>int</code>) – Results requested per entity search call.
- [**resolved_entity_top_k**](#agrag-retrieval-RetrievalSettings-resolved_entity_top_k) (<code>int</code>) – Results requested per resolved-entity search
  call.
- [**chunk_top_k**](#agrag-retrieval-RetrievalSettings-chunk_top_k) (<code>int</code>) – Results requested per chunk search call.
- [**hybrid_alpha**](#agrag-retrieval-RetrievalSettings-hybrid_alpha) (<code>float</code>) – Dense-versus-keyword blend for hybrid search,
  0 to 1. Only meaningful on the VectorStore path;
  GraphStore-native search is dense-only and ignores this.
- [**traversal_depth**](#agrag-retrieval-RetrievalSettings-traversal_depth) (<code>int</code>) – Maximum BFS hops from a seed entity.
- [**traversal_limit**](#agrag-retrieval-RetrievalSettings-traversal_limit) (<code>int</code>) – Maximum nodes a BFS expansion can return.
- [**rrf_k**](#agrag-retrieval-RetrievalSettings-rrf_k) (<code>int</code>) – The RRF constant controlling how much rank position
  matters.
- [**reranker_min_score**](#agrag-retrieval-RetrievalSettings-reranker_min_score) (<code>float | None</code>) – Results scoring below this after rerank
  are dropped. None disables the threshold.
- [**text2cypher_timeout_seconds**](#agrag-retrieval-RetrievalSettings-text2cypher_timeout_seconds) (<code>float | None</code>) – Server-side transaction timeout
  applied to generated read queries. The database terminates
  a generated query that runs longer, so a pathological
  query cannot hold server resources indefinitely. None
  uses the server's default timeout.
- [**text2cypher_max_rows**](#agrag-retrieval-RetrievalSettings-text2cypher_max_rows) (<code>int</code>) – Maximum rows a generated read query may
  return. Appended as a LIMIT clause when the generated
  query declares none of its own.
- [**cross_encoder_model**](#agrag-retrieval-RetrievalSettings-cross_encoder_model) (<code>str</code>) – The sentence-transformers CrossEncoder model
  used for cross_encoder reranking. Env:
  RETRIEVAL_CROSS_ENCODER_MODEL.
- [**community_collection**](#agrag-retrieval-RetrievalSettings-community_collection) (<code>str</code>) – The VectorStore collection name for community
  search. Same condition as entity_collection/chunk_collection:
  only read when a VectorStore is configured.
- [**community_top_k**](#agrag-retrieval-RetrievalSettings-community_top_k) (<code>int</code>) – Results requested per community search call when
  the caller passes no explicit limit -- the same role
  entity_top_k/chunk_top_k play for their retrievers. Distinct
  from Recipe.community_top_k (enrichment-budget/reserved-slice
  size): same name, different class, different job.

Env prefix: `RETRIEVAL_`.

#### `agrag.retrieval.RetrievalSettings.chunk_collection` \{#agrag-retrieval-RetrievalSettings-chunk_collection}

```python
chunk_collection: str = 'agrag_chunks'
```

#### `agrag.retrieval.RetrievalSettings.chunk_top_k` \{#agrag-retrieval-RetrievalSettings-chunk_top_k}

```python
chunk_top_k: int = 10
```

#### `agrag.retrieval.RetrievalSettings.community_collection` \{#agrag-retrieval-RetrievalSettings-community_collection}

```python
community_collection: str = 'agrag_communities'
```

#### `agrag.retrieval.RetrievalSettings.community_top_k` \{#agrag-retrieval-RetrievalSettings-community_top_k}

```python
community_top_k: int = 5
```

#### `agrag.retrieval.RetrievalSettings.cross_encoder_model` \{#agrag-retrieval-RetrievalSettings-cross_encoder_model}

```python
cross_encoder_model: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'
```

#### `agrag.retrieval.RetrievalSettings.entity_collection` \{#agrag-retrieval-RetrievalSettings-entity_collection}

```python
entity_collection: str = 'agrag_entities'
```

#### `agrag.retrieval.RetrievalSettings.entity_labels` \{#agrag-retrieval-RetrievalSettings-entity_labels}

```python
entity_labels: list[str] = []
```

#### `agrag.retrieval.RetrievalSettings.entity_top_k` \{#agrag-retrieval-RetrievalSettings-entity_top_k}

```python
entity_top_k: int = 10
```

#### `agrag.retrieval.RetrievalSettings.hybrid_alpha` \{#agrag-retrieval-RetrievalSettings-hybrid_alpha}

```python
hybrid_alpha: float = 0.5
```

#### `agrag.retrieval.RetrievalSettings.model_config` \{#agrag-retrieval-RetrievalSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='RETRIEVAL_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

#### `agrag.retrieval.RetrievalSettings.node_distance_seed_top_k` \{#agrag-retrieval-RetrievalSettings-node_distance_seed_top_k}

```python
node_distance_seed_top_k: int = 3
```

#### `agrag.retrieval.RetrievalSettings.reranker_min_score` \{#agrag-retrieval-RetrievalSettings-reranker_min_score}

```python
reranker_min_score: float | None = None
```

#### `agrag.retrieval.RetrievalSettings.resolved_entity_collection` \{#agrag-retrieval-RetrievalSettings-resolved_entity_collection}

```python
resolved_entity_collection: str = 'agrag_resolved_entities'
```

#### `agrag.retrieval.RetrievalSettings.resolved_entity_top_k` \{#agrag-retrieval-RetrievalSettings-resolved_entity_top_k}

```python
resolved_entity_top_k: int = 10
```

#### `agrag.retrieval.RetrievalSettings.rrf_k` \{#agrag-retrieval-RetrievalSettings-rrf_k}

```python
rrf_k: int = 60
```

#### `agrag.retrieval.RetrievalSettings.text2cypher_max_rows` \{#agrag-retrieval-RetrievalSettings-text2cypher_max_rows}

```python
text2cypher_max_rows: int = 1000
```

#### `agrag.retrieval.RetrievalSettings.text2cypher_timeout_seconds` \{#agrag-retrieval-RetrievalSettings-text2cypher_timeout_seconds}

```python
text2cypher_timeout_seconds: float | None = 10.0
```

#### `agrag.retrieval.RetrievalSettings.traversal_depth` \{#agrag-retrieval-RetrievalSettings-traversal_depth}

```python
traversal_depth: int = 2
```

#### `agrag.retrieval.RetrievalSettings.traversal_limit` \{#agrag-retrieval-RetrievalSettings-traversal_limit}

```python
traversal_limit: int = 50
```

### `agrag.retrieval.Retriever` \{#agrag-retrieval-Retriever}

Bases: <code>ABC</code>

One retrieval method: given a query, return SearchResults.

Subclasses own exactly one strategy (dense entity search, chunk
search, BFS expansion). SearchEngine fans a query out to every
Retriever a Recipe names and hands the combined output to Fusion.

**Functions:**

- [**retrieve**](#agrag-retrieval-Retriever-retrieve) – Run this retrieval method and return hydrated results.

**Attributes:**

- [**name**](#agrag-retrieval-Retriever-name) (<code>str</code>) –

#### `agrag.retrieval.Retriever.name` \{#agrag-retrieval-Retriever-name}

```python
name: str
```

#### `agrag.retrieval.Retriever.retrieve` \{#agrag-retrieval-Retriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int = 10) -> list[SearchResult]
```

Run this retrieval method and return hydrated results.

### `agrag.retrieval.ScopeDeniedError` \{#agrag-retrieval-ScopeDeniedError}

Bases: <code>[RetrievalError](#agrag-retrieval-errors-RetrievalError)</code>

A request asked for data outside the caller's permitted scope.

The caller's scope is an authorization boundary the requesting
layer can narrow but never widen. Raised instead of searching the
wider scope or silently running the request unrestricted, so a
caller can report the refusal rather than answer from data it was
never allowed to see.

### `agrag.retrieval.SearchEngine` \{#agrag-retrieval-SearchEngine}

```python
SearchEngine(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None, entity_labels:Sequence[str] | None = None, graph_schema:GraphSchema | None = None, tracer:Tracer | None = None) -> None
```

Retrieval's public entry point, independent of Graph.

Fans a query out to every method a Recipe names, fuses the
results, and optionally reranks them. Constructed from its own
stores; does not depend on a Graph instance existing.

A `tracer` opens the retrieval spans and flows to every
retriever and free function the engine calls. It is *not* pushed
into `graph_store`, `embedder` or `vector_store`: pass the
same tracer to those when you build them, so their adapter spans
nest under these retrieval spans.

**Functions:**

- [**find_entity**](#agrag-retrieval-SearchEngine-find_entity) – Resolve a named entity to its top search hit, or None.
- [**list_relationship_types**](#agrag-retrieval-SearchEngine-list_relationship_types) – List the relationship types directly attached to an entity.
- [**search**](#agrag-retrieval-SearchEngine-search) – Run recipe's methods, fuse, expand, and optionally rerank.
- [**traverse**](#agrag-retrieval-SearchEngine-traverse) – Expand one resolved entity into its neighbours.

**Attributes:**

- [**graph_schema**](#agrag-retrieval-SearchEngine-graph_schema) (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The schema retrieval is grounded in, GENERIC when none was given.

**Parameters:**

- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Always required; backs entity/chunk search
  when vector_store is absent, and always backs BFS.
- **embedder** (<code>[Embedder](embedding.md#agrag-embedding-base-Embedder)</code>) – Produces query vectors for dense and hybrid
  search.
- **vector_store** (<code>[VectorStore](vectordb.md#agrag-vectordb-base-VectorStore) | None</code>) – Optional. When set, entity, chunk, and
  community search run hybrid_search there instead of
  GraphStore's native search. `Graph.open(vector_store=...)`
  provisions the collections and dual-writes every embedding
  this package ingests, so the two paths see the same data.
  Point it at a store that `Graph.open` provisioned: a
  missing collection makes each method that reads it fail, and
  `search` raises `AllRetrievalMethodsFailedError` when
  every method fails. Collections that exist but hold no
  records return no hits.
- **settings** (<code>[RetrievalSettings](#agrag-retrieval-settings-RetrievalSettings) | None</code>) – Retrieval configuration; defaults from
  environment.
- **entity_labels** (<code>Sequence\[str\] | None</code>) – The entity labels native entity search runs
  against, one vector index each, as provisioned by
  `Graph.open`. Retained as a checked input only: it must
  name exactly the labels graph_schema declares, since the
  schema is what native search and generated Cypher both
  read. Omit it and let the schema drive both. Ignored when
  a vector_store is configured.
- **graph_schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema) | None</code>) – The graph's declared schema, ground truth for
  native entity labels and for generated Cypher. None uses
  `GENERIC`.
- **tracer** (<code>Tracer | None</code>) – Opens the search span and flows to every retriever
  and free function the engine calls. None opens no
  recorded span.

**Raises:**

- <code>ValueError</code> – entity_labels does not name exactly the labels
  graph_schema declares.

#### `agrag.retrieval.SearchEngine.find_entity` \{#agrag-retrieval-SearchEngine-find_entity}

```python
find_entity(name:str, *, filters:SearchFilters | None = None) -> SearchResult | None
```

Resolve a named entity to its top search hit, or None.

Searches this engine's configured entity_labels by default. A
filters.labels value, when set, overrides which labels are
searched rather than narrowing within entity_labels -- the same
EntityRetriever behavior search()'s own entity search already
relies on.

**Parameters:**

- **name** (<code>str</code>) – The entity name (or description) to resolve.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Scope to resolve within. An entity that exists
  only outside it resolves to None, the same as one that
  does not exist.

**Returns:**

- <code>[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult) | None</code> – The top-ranked SearchResult, or None when nothing matched.

#### `agrag.retrieval.SearchEngine.graph_schema` \{#agrag-retrieval-SearchEngine-graph_schema}

```python
graph_schema: GraphSchema
```

The schema retrieval is grounded in, GENERIC when none was given.

#### `agrag.retrieval.SearchEngine.list_relationship_types` \{#agrag-retrieval-SearchEngine-list_relationship_types}

```python
list_relationship_types(seed:SearchResult, *, relation_type_filter:str | None = None, direction:TraversalDirection = 'both', filters:SearchFilters | None = None) -> list[str]
```

List the relationship types directly attached to an entity.

Depth-1 only: it reports what is attached to the seed, never
what lies past it.

**Parameters:**

- **seed** (<code>[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)</code>) – The resolved entity to read attached types from,
  normally from :meth:`find_entity`.
- **relation_type_filter** (<code>str | None</code>) – Only report this type, if present.
- **direction** (<code>TraversalDirection</code>) – Which way to inspect relationships, relative to the
  seed entity.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Scope that limits visible relationship types.

**Returns:**

- <code>list\[str\]</code> – The distinct attached relationship type names.

#### `agrag.retrieval.SearchEngine.search` \{#agrag-retrieval-SearchEngine-search}

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
- **recipe** (<code>[Recipe](#agrag-retrieval-recipes-Recipe)</code>) – Which methods to run, whether to expand via BFS
  afterward, and which reranker, if any, follows.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Constraints applied identically to every method.

**Returns:**

- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – Up to recipe.limit results, ranked highest-relevance
- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – first.

**Raises:**

- <code>[AllRetrievalMethodsFailedError](#agrag-retrieval-errors-AllRetrievalMethodsFailedError)</code> – Every method the recipe
  names failed. A method failing while others succeed
  is logged and its results are simply absent.
- <code>[UnknownRecipeMethodError](#agrag-retrieval-errors-UnknownRecipeMethodError)</code> – The recipe names one or more
  methods that are not in the retriever registry. A
  misspelled method name is a configuration error and
  is reported instead of silently returning no
  results.

#### `agrag.retrieval.SearchEngine.traverse` \{#agrag-retrieval-SearchEngine-traverse}

```python
traverse(seed:SearchResult, *, relation_type:str | None = None, direction:TraversalDirection = 'both', depth:int = 1, limit:int = 10, community_expand:bool = False, community_top_k:int = 3, filters:SearchFilters | None = None) -> list[SearchResult]
```

Expand one resolved entity into its neighbours.

**Parameters:**

- **seed** (<code>[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)</code>) – The resolved entity to expand from, normally from
  :meth:`find_entity`.
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
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Scope for the traversal. Its `relation_types` is
  an allowlist a `relation_type` argument cannot widen;
  its `properties`, `document_ids`, and `labels`
  constrain returned neighbour nodes.

**Returns:**

- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – The neighbouring entities, deduplicated, highest-ranked
- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – first, with any requested community reports fused in.

**Raises:**

- <code>[ScopeDeniedError](#agrag-retrieval-errors-ScopeDeniedError)</code> – relation_type names a type the caller's
  scope does not permit.

### `agrag.retrieval.SearchFilters` \{#agrag-retrieval-SearchFilters}

Bases: <code>BaseModel</code>

Constraints applied across every retrieval method in one call.

**Attributes:**

- [**labels**](#agrag-retrieval-SearchFilters-labels) (<code>list\[str\]</code>) – Entity labels a result must have, when searching
  entities.
- [**relation_types**](#agrag-retrieval-SearchFilters-relation_types) (<code>list\[str\]</code>) – Relation types a traversal may cross.
- [**document_ids**](#agrag-retrieval-SearchFilters-document_ids) (<code>list\[str\]</code>) – Restrict results to entities and chunks from these
  source documents.
- [**properties**](#agrag-retrieval-SearchFilters-properties) (<code>dict\[str, Any\]</code>) – Exact-match property filters, applied
  identically to vector-store payload filters and Cypher
  WHERE clauses.

**Functions:**

- [**to_cypher_where**](#agrag-retrieval-SearchFilters-to_cypher_where) – Return a parameterized WHERE clause fragment.
- [**to_payload_filter**](#agrag-retrieval-SearchFilters-to_payload_filter) – Return a flat-dict filter for VectorStore search calls.
- [**to_property_filter**](#agrag-retrieval-SearchFilters-to_property_filter) – Return a flat-dict filter over node properties only.

#### `agrag.retrieval.SearchFilters.document_ids` \{#agrag-retrieval-SearchFilters-document_ids}

```python
document_ids: list[str] = Field(default_factory=list)
```

#### `agrag.retrieval.SearchFilters.labels` \{#agrag-retrieval-SearchFilters-labels}

```python
labels: list[str] = Field(default_factory=list)
```

#### `agrag.retrieval.SearchFilters.properties` \{#agrag-retrieval-SearchFilters-properties}

```python
properties: dict[str, Any] = Field(default_factory=dict)
```

#### `agrag.retrieval.SearchFilters.relation_types` \{#agrag-retrieval-SearchFilters-relation_types}

```python
relation_types: list[str] = Field(default_factory=list)
```

#### `agrag.retrieval.SearchFilters.to_cypher_where` \{#agrag-retrieval-SearchFilters-to_cypher_where}

```python
to_cypher_where(node_var:str = 'node') -> tuple[str, dict[str, Any]]
```

Return a parameterized WHERE clause fragment.

Labels are emitted as native Cypher node labels (`node:Label`)
rather than property filters, since Neo4j represents entity types
as labels on nodes. Document-id and property filters go through
`filter_clause` as before.

**Parameters:**

- **node_var** (<code>str</code>) – The Cypher variable bound to the node.

**Returns:**

- <code>tuple\[str, dict\[str, Any\]\]</code> – The WHERE clause text and parameters dict.

#### `agrag.retrieval.SearchFilters.to_payload_filter` \{#agrag-retrieval-SearchFilters-to_payload_filter}

```python
to_payload_filter() -> dict[str, Any]
```

Return a flat-dict filter for VectorStore search calls.

Labels become a `label` payload key, which is how a
VectorStore records the graph label a record came from. A
GraphStore holds labels on the node itself, not as a property,
so the native path uses `to_property_filter` instead and
selects labels by the index it searches.

**Returns:**

- <code>dict\[str, Any\]</code> – A dict suitable for VectorStore.search/hybrid_search
- <code>dict\[str, Any\]</code> – filters parameter.

#### `agrag.retrieval.SearchFilters.to_property_filter` \{#agrag-retrieval-SearchFilters-to_property_filter}

```python
to_property_filter() -> dict[str, Any]
```

Return a flat-dict filter over node properties only.

Excludes `labels`, which are node labels rather than
properties on every graph backend this project supports.

**Returns:**

- <code>dict\[str, Any\]</code> – A dict of property name to expected value, where a list
- <code>dict\[str, Any\]</code> – value means any of.

### `agrag.retrieval.TEXT2CYPHER` \{#agrag-retrieval-TEXT2CYPHER}

```python
TEXT2CYPHER = Recipe(methods=['text2cypher'], limit=10)
```

### `agrag.retrieval.THEMATIC` \{#agrag-retrieval-THEMATIC}

```python
THEMATIC = Recipe(methods=['community'], limit=5)
```

### `agrag.retrieval.Text2CypherRetriever` \{#agrag-retrieval-Text2CypherRetriever}

```python
Text2CypherRetriever(*, graph_store:GraphStore, schema:GraphSchema, settings:RetrievalSettings | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Retriever](#agrag-retrieval-retrievers-base-Retriever)</code>

Let the agent ask structured questions via generated Cypher.

Calls a BAML function to generate a read-only Cypher query
against the graph's declared schema, runs reject_write_cypher as a
safety pre-filter, then bounds the query with a row limit and a
server-side transaction timeout before EXPLAIN and execution. A
query that fails to plan or to execute is regenerated once, carrying
a bounded, sanitized diagnostic of the failure. Rows that carry an
entity id are hydrated from the graph before becoming a
SearchResult; relationship and chunk rows are parsed directly, under
the prompt's own aliases or any alias the model chose instead.
Scalar rows (for example counts or property values) become cited
`QueryValue` results so direct-query answers are not lost.

**Functions:**

- [**retrieve**](#agrag-retrieval-Text2CypherRetriever-retrieve) – Generate and execute a Cypher query for the question.

**Attributes:**

- [**name**](#agrag-retrieval-Text2CypherRetriever-name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Where the generated query runs.
- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The graph's declared schema. Generation is grounded in
  this schema's labels and relation patterns, so a query the
  graph cannot answer is not generated.
- **settings** (<code>[RetrievalSettings](#agrag-retrieval-settings-RetrievalSettings) | None</code>) – Retrieval configuration; defaults from
  environment.
- **tracer** (<code>Tracer | None</code>) – Opens the generation span and the BAML call spans.

#### `agrag.retrieval.Text2CypherRetriever.name` \{#agrag-retrieval-Text2CypherRetriever-name}

```python
name = 'text2cypher'
```

#### `agrag.retrieval.Text2CypherRetriever.retrieve` \{#agrag-retrieval-Text2CypherRetriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int = 10) -> list[SearchResult]
```

Generate and execute a Cypher query for the question.

A query that fails to plan or to execute is regenerated once, with a
bounded, sanitized diagnostic of the first failure attached to the
generation call. A failure at any stage of the second attempt, or a
query rejected by the write gate, returns no results rather than
raising.

**Parameters:**

- **query** (<code>str</code>) – The natural-language question.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Ignored; text2cypher applies its own filters.
- **limit** (<code>int</code>) – Maximum results to return.

**Returns:**

- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – SearchResults from the generated query: entity results
  hydrated from the graph; relation, chunk, and
  scalar rows parsed directly.

### `agrag.retrieval.UnknownRecipeMethodError` \{#agrag-retrieval-UnknownRecipeMethodError}

```python
UnknownRecipeMethodError(unknown:list[str], known:list[str]) -> None
```

Bases: <code>[RetrievalError](#agrag-retrieval-errors-RetrievalError)</code>

A Recipe named a method SearchEngine does not know how to run.

A misspelled method name is a configuration error and must be
raised at search time so an empty successful search cannot
silently hide a typo.

**Attributes:**

- [**unknown**](#agrag-retrieval-UnknownRecipeMethodError-unknown) – The method names the recipe listed that are not in
  the retriever registry.
- [**known**](#agrag-retrieval-UnknownRecipeMethodError-known) – The method names this SearchEngine can run.

#### `agrag.retrieval.UnknownRecipeMethodError.known` \{#agrag-retrieval-UnknownRecipeMethodError-known}

```python
known = list(known)
```

#### `agrag.retrieval.UnknownRecipeMethodError.unknown` \{#agrag-retrieval-UnknownRecipeMethodError-unknown}

```python
unknown = list(unknown)
```

### `agrag.retrieval.community_context` \{#agrag-retrieval-community_context}

Community-report enrichment: local-search-style budget-capped context.

**Functions:**

- [**community_context**](#agrag-retrieval-community_context-community_context) – Return the top-overlapping communities' reports for a set of entities.
- [**expand_with_communities**](#agrag-retrieval-community_context-expand_with_communities) – Fuse community reports overlapping seed entities into a result list.

**Attributes:**

- [**logger**](#agrag-retrieval-community_context-logger) –

#### `agrag.retrieval.community_context.community_context` \{#agrag-retrieval-community_context-community_context}

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
- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Where the overlap lookup runs.
- **top_k** (<code>int</code>) – The maximum number of communities to return. Zero or
  negative returns no results without querying.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Applied to the candidate community node via
  `document_ids`/`properties` (`to_cypher_where`); labels
  are not applied, since they check node labels and a Community
  node never carries an entity label. Community nodes carry no
  document or tenant scope of their own, so a filter naming a
  property Community nodes never have matches no communities --
  a document- or property-scoped search gets no community
  enrichment rather than one drawn from outside its scope.
- **tracer** (<code>Tracer | None</code>) – Opens the context span. None opens no recorded span.

**Returns:**

- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – Up to top_k SearchResults wrapping Community items, highest overlap
- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – first. Empty when entity_ids is empty or no community overlaps.

#### `agrag.retrieval.community_context.expand_with_communities` \{#agrag-retrieval-community_context-expand_with_communities}

```python
expand_with_communities(fused:list[SearchResult], seed_ids:list[UUID], *, graph_store:GraphStore, top_k:int, filters:SearchFilters | None, rrf_k:int, tracer:Tracer | None = None) -> list[SearchResult]
```

Fuse community reports overlapping seed entities into a result list.

A convenience over :func:`community_context`: looks up the communities
that overlap `seed_ids` and fuses whatever comes back into `fused`
under a `"community"` key, so callers that already have a fused
result list do not repeat the fetch-then-fuse pattern (or the
error handling below).

A community lookup that raises is recorded on the expansion span and
swallowed rather than propagating: community reports are enrichment on
top of results that already exist, so a community-store failure must
not discard them.

**Parameters:**

- **fused** (<code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code>) – The already-fused results to enrich. Returned unchanged
  when no community overlaps the seeds.
- **seed_ids** (<code>list\[UUID\]</code>) – The entity ids to look for overlapping communities.
- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Where the overlap lookup runs.
- **top_k** (<code>int</code>) – The maximum number of communities to add.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Applied to the candidate community node; see
  :func:`community_context` for what a scoped filter does and
  does not match. Community nodes carry no entity label and no
  document scope of their own, so a document- or
  property-scoped caller gets no community enrichment at all --
  consistent with a plain search, not an error.
- **rrf_k** (<code>int</code>) – The reciprocal-rank-fusion constant, from
  `RetrievalSettings.rrf_k`.
- **tracer** (<code>Tracer | None</code>) – Opens the expansion spans. None opens no recorded span.

**Returns:**

- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – `fused` with the overlapping communities fused in, or `fused`
- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – itself when there were none.

#### `agrag.retrieval.community_context.logger` \{#agrag-retrieval-community_context-logger}

```python
logger = logging.getLogger(__name__)
```

### `agrag.retrieval.errors` \{#agrag-retrieval-errors}

Errors that the retrieval layer raises.

**Classes:**

- [**AllRetrievalMethodsFailedError**](#agrag-retrieval-errors-AllRetrievalMethodsFailedError) – Every retrieval method a Recipe named failed.
- [**RetrievalError**](#agrag-retrieval-errors-RetrievalError) – The base class for every retrieval error.
- [**ScopeDeniedError**](#agrag-retrieval-errors-ScopeDeniedError) – A request asked for data outside the caller's permitted scope.
- [**UnknownRecipeMethodError**](#agrag-retrieval-errors-UnknownRecipeMethodError) – A Recipe named a method SearchEngine does not know how to run.

#### `agrag.retrieval.errors.AllRetrievalMethodsFailedError` \{#agrag-retrieval-errors-AllRetrievalMethodsFailedError}

```python
AllRetrievalMethodsFailedError(failures:dict[str, BaseException]) -> None
```

Bases: <code>[RetrievalError](#agrag-retrieval-errors-RetrievalError)</code>

Every retrieval method a Recipe named failed.

Raised instead of returning an empty result list so a total
retrieval outage is not mistaken for a query with no matches.

**Attributes:**

- [**failures**](#agrag-retrieval-errors-AllRetrievalMethodsFailedError-failures) – Each failed method name mapped to the exception it
  raised.

##### `agrag.retrieval.errors.AllRetrievalMethodsFailedError.failures` \{#agrag-retrieval-errors-AllRetrievalMethodsFailedError-failures}

```python
failures = failures
```

#### `agrag.retrieval.errors.RetrievalError` \{#agrag-retrieval-errors-RetrievalError}

Bases: <code>Exception</code>

The base class for every retrieval error.

#### `agrag.retrieval.errors.ScopeDeniedError` \{#agrag-retrieval-errors-ScopeDeniedError}

Bases: <code>[RetrievalError](#agrag-retrieval-errors-RetrievalError)</code>

A request asked for data outside the caller's permitted scope.

The caller's scope is an authorization boundary the requesting
layer can narrow but never widen. Raised instead of searching the
wider scope or silently running the request unrestricted, so a
caller can report the refusal rather than answer from data it was
never allowed to see.

#### `agrag.retrieval.errors.UnknownRecipeMethodError` \{#agrag-retrieval-errors-UnknownRecipeMethodError}

```python
UnknownRecipeMethodError(unknown:list[str], known:list[str]) -> None
```

Bases: <code>[RetrievalError](#agrag-retrieval-errors-RetrievalError)</code>

A Recipe named a method SearchEngine does not know how to run.

A misspelled method name is a configuration error and must be
raised at search time so an empty successful search cannot
silently hide a typo.

**Attributes:**

- [**unknown**](#agrag-retrieval-errors-UnknownRecipeMethodError-unknown) – The method names the recipe listed that are not in
  the retriever registry.
- [**known**](#agrag-retrieval-errors-UnknownRecipeMethodError-known) – The method names this SearchEngine can run.

##### `agrag.retrieval.errors.UnknownRecipeMethodError.known` \{#agrag-retrieval-errors-UnknownRecipeMethodError-known}

```python
known = list(known)
```

##### `agrag.retrieval.errors.UnknownRecipeMethodError.unknown` \{#agrag-retrieval-errors-UnknownRecipeMethodError-unknown}

```python
unknown = list(unknown)
```

### `agrag.retrieval.filters` \{#agrag-retrieval-filters}

Constraints applied across every retrieval method in one call.

**Classes:**

- [**SearchFilters**](#agrag-retrieval-filters-SearchFilters) – Constraints applied across every retrieval method in one call.

#### `agrag.retrieval.filters.SearchFilters` \{#agrag-retrieval-filters-SearchFilters}

Bases: <code>BaseModel</code>

Constraints applied across every retrieval method in one call.

**Attributes:**

- [**labels**](#agrag-retrieval-filters-SearchFilters-labels) (<code>list\[str\]</code>) – Entity labels a result must have, when searching
  entities.
- [**relation_types**](#agrag-retrieval-filters-SearchFilters-relation_types) (<code>list\[str\]</code>) – Relation types a traversal may cross.
- [**document_ids**](#agrag-retrieval-filters-SearchFilters-document_ids) (<code>list\[str\]</code>) – Restrict results to entities and chunks from these
  source documents.
- [**properties**](#agrag-retrieval-filters-SearchFilters-properties) (<code>dict\[str, Any\]</code>) – Exact-match property filters, applied
  identically to vector-store payload filters and Cypher
  WHERE clauses.

**Functions:**

- [**to_cypher_where**](#agrag-retrieval-filters-SearchFilters-to_cypher_where) – Return a parameterized WHERE clause fragment.
- [**to_payload_filter**](#agrag-retrieval-filters-SearchFilters-to_payload_filter) – Return a flat-dict filter for VectorStore search calls.
- [**to_property_filter**](#agrag-retrieval-filters-SearchFilters-to_property_filter) – Return a flat-dict filter over node properties only.

##### `agrag.retrieval.filters.SearchFilters.document_ids` \{#agrag-retrieval-filters-SearchFilters-document_ids}

```python
document_ids: list[str] = Field(default_factory=list)
```

##### `agrag.retrieval.filters.SearchFilters.labels` \{#agrag-retrieval-filters-SearchFilters-labels}

```python
labels: list[str] = Field(default_factory=list)
```

##### `agrag.retrieval.filters.SearchFilters.properties` \{#agrag-retrieval-filters-SearchFilters-properties}

```python
properties: dict[str, Any] = Field(default_factory=dict)
```

##### `agrag.retrieval.filters.SearchFilters.relation_types` \{#agrag-retrieval-filters-SearchFilters-relation_types}

```python
relation_types: list[str] = Field(default_factory=list)
```

##### `agrag.retrieval.filters.SearchFilters.to_cypher_where` \{#agrag-retrieval-filters-SearchFilters-to_cypher_where}

```python
to_cypher_where(node_var:str = 'node') -> tuple[str, dict[str, Any]]
```

Return a parameterized WHERE clause fragment.

Labels are emitted as native Cypher node labels (`node:Label`)
rather than property filters, since Neo4j represents entity types
as labels on nodes. Document-id and property filters go through
`filter_clause` as before.

**Parameters:**

- **node_var** (<code>str</code>) – The Cypher variable bound to the node.

**Returns:**

- <code>tuple\[str, dict\[str, Any\]\]</code> – The WHERE clause text and parameters dict.

##### `agrag.retrieval.filters.SearchFilters.to_payload_filter` \{#agrag-retrieval-filters-SearchFilters-to_payload_filter}

```python
to_payload_filter() -> dict[str, Any]
```

Return a flat-dict filter for VectorStore search calls.

Labels become a `label` payload key, which is how a
VectorStore records the graph label a record came from. A
GraphStore holds labels on the node itself, not as a property,
so the native path uses `to_property_filter` instead and
selects labels by the index it searches.

**Returns:**

- <code>dict\[str, Any\]</code> – A dict suitable for VectorStore.search/hybrid_search
- <code>dict\[str, Any\]</code> – filters parameter.

##### `agrag.retrieval.filters.SearchFilters.to_property_filter` \{#agrag-retrieval-filters-SearchFilters-to_property_filter}

```python
to_property_filter() -> dict[str, Any]
```

Return a flat-dict filter over node properties only.

Excludes `labels`, which are node labels rather than
properties on every graph backend this project supports.

**Returns:**

- <code>dict\[str, Any\]</code> – A dict of property name to expected value, where a list
- <code>dict\[str, Any\]</code> – value means any of.

### `agrag.retrieval.fusion` \{#agrag-retrieval-fusion}

Reciprocal Rank Fusion: combine ranked results from multiple methods.

**Functions:**

- [**fuse**](#agrag-retrieval-fusion-fuse) – Combine every method's ranked results into one deduplicated list.

#### `agrag.retrieval.fusion.fuse` \{#agrag-retrieval-fusion-fuse}

```python
fuse(results_by_method:dict[str, list[SearchResult]], *, rrf_k:int = 60, tracer:Tracer | None = None) -> list[SearchResult]
```

Combine every method's ranked results into one deduplicated list.

Runs unconditionally, even for a single method, so a Rerank pass
never sees duplicates. Uses Reciprocal Rank Fusion: an item's
fused score is the sum of 1 / (rrf_k + rank) across every method
that returned it.

Each method contributes at most one vote per item, scored at the
item's best (lowest) rank within that method. A multi-label
entity that surfaces in two positions of one method's output only
adds one vote from that method, so duplicate hits from a single
retriever cannot unfairly promote an item over a single best hit
from another method.

Deduplication uses SearchResult.identity_key, which is (type, id).
Fusion does not re-resolve identity; it deduplicates on the ids each
SearchResult carries.

**Parameters:**

- **results_by_method** (<code>dict\[str, list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]\]</code>) – Each method's own ranked output, keyed by
  method name.
- **rrf_k** (<code>int</code>) – The RRF constant; higher values flatten the influence
  of rank position.
- **tracer** (<code>Tracer | None</code>) – Opens the fusion span. None opens no recorded span.

**Returns:**

- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – One list, ranked by fused score descending, one entry per
- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – distinct identity_key.

### `agrag.retrieval.methods` \{#agrag-retrieval-methods}

Low-level search method helpers shared by retrievers.

**Modules:**

- [**traversal**](#agrag-retrieval-methods-traversal) – Entity resolution and seeded traversal, callable without a SearchEngine.
- [**vector**](#agrag-retrieval-methods-vector) – Shared vector search helper for GraphStore and VectorStore.

#### `agrag.retrieval.methods.traversal` \{#agrag-retrieval-methods-traversal}

Entity resolution and seeded traversal, callable without a SearchEngine.

Free functions, not methods, for the same reason `vector.py`'s
`vector_search` is: the retrieval building blocks stay independently
testable and `SearchEngine` stays an orchestrator over them.

**Functions:**

- [**extract_entity_ids**](#agrag-retrieval-methods-traversal-extract_entity_ids) – Return raw entity ids from results, preserving order.
- [**find_entity**](#agrag-retrieval-methods-traversal-find_entity) – Resolve a named entity to its top search hit, or None.
- [**list_relationship_types**](#agrag-retrieval-methods-traversal-list_relationship_types) – List the relationship types directly attached to a resolved entity.
- [**traverse**](#agrag-retrieval-methods-traversal-traverse) – Expand one resolved entity into its neighbours.

**Attributes:**

- [**logger**](#agrag-retrieval-methods-traversal-logger) –

##### `agrag.retrieval.methods.traversal.extract_entity_ids` \{#agrag-retrieval-methods-traversal-extract_entity_ids}

```python
extract_entity_ids(results:list[SearchResult]) -> list[UUID]
```

Return raw entity ids from results, preserving order.

Used for BFS seeds and node-distance reranking. Keeps the
first-seen id of each entity so the fusion ranking is respected. A
ResolvedEntity contributes its raw member ids, since graph
traversal and distance run over raw entity nodes: a resolved
entity's own id names no `_AgragNode` an entity traversal can
start from, so seeding with it would silently match nothing.
Chunks and other non-entity result items are skipped.

**Parameters:**

- **results** (<code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code>) – The result list to read entity ids from.

**Returns:**

- <code>list\[UUID\]</code> – Each entity id once, in first-seen order.

##### `agrag.retrieval.methods.traversal.find_entity` \{#agrag-retrieval-methods-traversal-find_entity}

```python
find_entity(name:str, *, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None, settings:RetrievalSettings, entity_labels:Sequence[str], filters:SearchFilters | None = None, tracer:Tracer | None = None) -> SearchResult | None
```

Resolve a named entity to its top search hit, or None.

Runs one entity search and returns its best result, which callers
keep whole rather than unwrapping: the item renders as evidence,
and the result itself is what :func:`extract_entity_ids` can turn
into traversal seeds.

**Parameters:**

- **name** (<code>str</code>) – The entity name (or description) to resolve.
- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Backs entity search when vector_store is absent.
- **embedder** (<code>[Embedder](embedding.md#agrag-embedding-base-Embedder)</code>) – Produces the query vector.
- **vector_store** (<code>[VectorStore](vectordb.md#agrag-vectordb-base-VectorStore) | None</code>) – Optional vector store for hybrid search.
- **settings** (<code>[RetrievalSettings](#agrag-retrieval-settings-RetrievalSettings)</code>) – Retrieval configuration.
- **entity_labels** (<code>Sequence\[str\]</code>) – The labels native entity search runs against by
  default, one vector index each.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Scope to resolve within. Labels, document ids, and
  `properties` are projected through, matching the
  projection a plain search's own entity step applies; a
  `filters.labels` value replaces `entity_labels` rather
  than narrowing within it, so a scope carrying only
  unrelated fields must not be mistaken for a deliberate
  label override. An entity that exists only outside this
  scope resolves to None, the same as one that does not
  exist.
- **tracer** (<code>Tracer | None</code>) – Opens the root span and flows to the entity retriever.
  None opens no recorded span.

**Returns:**

- <code>[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult) | None</code> – The top-ranked SearchResult, or None when nothing matched.

##### `agrag.retrieval.methods.traversal.list_relationship_types` \{#agrag-retrieval-methods-traversal-list_relationship_types}

```python
list_relationship_types(seed:SearchResult, *, graph_store:GraphStore, relation_type_filter:str | None = None, direction:TraversalDirection = 'both', filters:SearchFilters | None = None, tracer:Tracer | None = None) -> list[str]
```

List the relationship types directly attached to a resolved entity.

Depth-1 only: it reports what is attached to the seed, never what
lies past it. Any relation type allowlist in `filters` is applied
before the query runs.

**Parameters:**

- **seed** (<code>[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)</code>) – The resolved entity to read attached types from.
- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – The graph to read.
- **relation_type_filter** (<code>str | None</code>) – Only report this type, if present.
- **direction** (<code>TraversalDirection</code>) – Which way to inspect relationships, relative to the seed.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Scope that limits which relationship types are visible.
- **tracer** (<code>Tracer | None</code>) – Opens the root span. None opens no recorded span.

**Returns:**

- <code>list\[str\]</code> – The distinct attached relationship type names.

##### `agrag.retrieval.methods.traversal.logger` \{#agrag-retrieval-methods-traversal-logger}

```python
logger = logging.getLogger(__name__)
```

##### `agrag.retrieval.methods.traversal.traverse` \{#agrag-retrieval-methods-traversal-traverse}

```python
traverse(seed:SearchResult, *, graph_store:GraphStore, settings:RetrievalSettings, relation_type:str | None = None, direction:TraversalDirection = 'both', depth:int = 1, limit:int = 10, community_expand:bool = False, community_top_k:int = 3, filters:SearchFilters | None = None, tracer:Tracer | None = None) -> list[SearchResult]
```

Expand one resolved entity into its neighbours.

**Parameters:**

- **seed** (<code>[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)</code>) – The resolved entity to expand from. A ResolvedEntity seed
  expands from its raw member ids, never its own id.
- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – The graph to traverse.
- **settings** (<code>[RetrievalSettings](#agrag-retrieval-settings-RetrievalSettings)</code>) – Retrieval configuration, carrying the BFS defaults
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
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Scope for the traversal. `relation_types` here is an
  immutable allowlist the caller set, not something a
  `relation_type` argument can widen: a request outside it
  is refused without querying the graph. `properties`
  `document_ids`, and `labels` constrain returned
  neighbour nodes.
- **tracer** (<code>Tracer | None</code>) – Opens the root span and flows to the BFS retriever and
  community expansion. None opens no recorded span.

**Returns:**

- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – The neighbouring entities, deduplicated, highest-ranked first,
- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – with any requested community reports fused in.

**Raises:**

- <code>[ScopeDeniedError](#agrag-retrieval-errors-ScopeDeniedError)</code> – relation_type names a type the caller's scope
  does not permit.

#### `agrag.retrieval.methods.vector` \{#agrag-retrieval-methods-vector}

Shared vector search helper for GraphStore and VectorStore.

**Functions:**

- [**vector_search**](#agrag-retrieval-methods-vector-vector_search) – Embed query and search on whichever store is configured.

##### `agrag.retrieval.methods.vector.vector_search` \{#agrag-retrieval-methods-vector-vector_search}

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
- **embedder** (<code>[Embedder](embedding.md#agrag-embedding-base-Embedder)</code>) – Produces the query's dense vector.
- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – The GraphStore-native fallback target.
- **vector_store** (<code>[VectorStore](vectordb.md#agrag-vectordb-base-VectorStore) | None</code>) – The optional VectorStore target; None selects
  the GraphStore-native path.
- **collection** (<code>str</code>) – The VectorStore collection name.
- **labels** (<code>Sequence\[str\]</code>) – The node labels to search on the GraphStore-native
  path, each backed by its own vector index.
- **limit** (<code>int</code>) – Maximum hits to return.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Constraints translated to whichever store is
  searched. Labels are a payload key on the VectorStore
  path and choose the searched indexes on the native path,
  so they are not sent as node property filters.
- **settings** (<code>[RetrievalSettings](#agrag-retrieval-settings-RetrievalSettings)</code>) – Supplies hybrid_alpha for the VectorStore path.
- **query_vector** (<code>Sequence\[float\] | None</code>) – Precomputed query embedding. None embeds `query`.
- **tracer** (<code>Tracer | None</code>) – Opens the search span. None opens no recorded span.

**Returns:**

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – Ranked VectorHits, from whichever store was searched.

**Raises:**

- <code>ValueError</code> – The native path was selected with no labels to
  search.

### `agrag.retrieval.recipes` \{#agrag-retrieval-recipes}

Named, data-only configurations of what SearchEngine runs.

**Classes:**

- [**Recipe**](#agrag-retrieval-recipes-Recipe) – A named configuration of what SearchEngine runs for a query.

**Attributes:**

- [**CHUNK**](#agrag-retrieval-recipes-CHUNK) –
- [**ENTITY**](#agrag-retrieval-recipes-ENTITY) –
- [**GRAPH_EXPAND**](#agrag-retrieval-recipes-GRAPH_EXPAND) –
- [**HYBRID**](#agrag-retrieval-recipes-HYBRID) –
- [**HYBRID_RERANKED**](#agrag-retrieval-recipes-HYBRID_RERANKED) –
- [**TEXT2CYPHER**](#agrag-retrieval-recipes-TEXT2CYPHER) –
- [**THEMATIC**](#agrag-retrieval-recipes-THEMATIC) –

#### `agrag.retrieval.recipes.CHUNK` \{#agrag-retrieval-recipes-CHUNK}

```python
CHUNK = Recipe(methods=['chunk'], limit=10)
```

#### `agrag.retrieval.recipes.ENTITY` \{#agrag-retrieval-recipes-ENTITY}

```python
ENTITY = Recipe(methods=['entity'], limit=10)
```

#### `agrag.retrieval.recipes.GRAPH_EXPAND` \{#agrag-retrieval-recipes-GRAPH_EXPAND}

```python
GRAPH_EXPAND = Recipe(methods=['entity'], bfs=True, limit=20, community_expand=True)
```

#### `agrag.retrieval.recipes.HYBRID` \{#agrag-retrieval-recipes-HYBRID}

```python
HYBRID = Recipe(methods=['entity', 'chunk'], limit=10)
```

#### `agrag.retrieval.recipes.HYBRID_RERANKED` \{#agrag-retrieval-recipes-HYBRID_RERANKED}

```python
HYBRID_RERANKED = Recipe(methods=['entity', 'chunk'], reranker='cross_encoder', limit=10, community_expand=True)
```

#### `agrag.retrieval.recipes.Recipe` \{#agrag-retrieval-recipes-Recipe}

Bases: <code>BaseModel</code>

A named configuration of what SearchEngine runs for a query.

**Attributes:**

- [**methods**](#agrag-retrieval-recipes-Recipe-methods) (<code>list\[str\]</code>) – Which retrieval methods to fan out to
  concurrently, by name.
- [**bfs**](#agrag-retrieval-recipes-Recipe-bfs) (<code>bool</code>) – Whether to run a BFS expansion after methods
  complete, seeded from their entity results. BFS
  needs seed ids methods produce, so it cannot run
  concurrently with them.
- [**bfs_depth**](#agrag-retrieval-recipes-Recipe-bfs_depth) (<code>int | None</code>) – Traversal depth when bfs is true. None uses
  RetrievalSettings.traversal_depth.
- [**reranker**](#agrag-retrieval-recipes-Recipe-reranker) (<code>Literal['cross_encoder', 'node_distance'] | None</code>) – The optional Rerank pass to run after Fusion.
  None skips reranking.
- [**min_score**](#agrag-retrieval-recipes-Recipe-min_score) (<code>float | None</code>) – Results the reranker scores below this are dropped.
  None uses RetrievalSettings.reranker_min_score, so a caller
  can tighten the floor for one call without touching the
  configured default.
- [**limit**](#agrag-retrieval-recipes-Recipe-limit) (<code>int</code>) – The maximum number of results SearchEngine
  returns.
- [**community_expand**](#agrag-retrieval-recipes-Recipe-community_expand) (<code>bool</code>) – Whether to fetch and fuse in overlapping
  communities' reports after BFS.
- [**community_top_k**](#agrag-retrieval-recipes-Recipe-community_top_k) (<code>int</code>) – How many communities community_context
  returns, and (when reranker is cross_encoder) how many
  are reserved a slot after rerank.

##### `agrag.retrieval.recipes.Recipe.bfs` \{#agrag-retrieval-recipes-Recipe-bfs}

```python
bfs: bool = False
```

##### `agrag.retrieval.recipes.Recipe.bfs_depth` \{#agrag-retrieval-recipes-Recipe-bfs_depth}

```python
bfs_depth: int | None = None
```

##### `agrag.retrieval.recipes.Recipe.community_expand` \{#agrag-retrieval-recipes-Recipe-community_expand}

```python
community_expand: bool = False
```

##### `agrag.retrieval.recipes.Recipe.community_top_k` \{#agrag-retrieval-recipes-Recipe-community_top_k}

```python
community_top_k: int = 3
```

##### `agrag.retrieval.recipes.Recipe.limit` \{#agrag-retrieval-recipes-Recipe-limit}

```python
limit: int = 10
```

##### `agrag.retrieval.recipes.Recipe.methods` \{#agrag-retrieval-recipes-Recipe-methods}

```python
methods: list[str]
```

##### `agrag.retrieval.recipes.Recipe.min_score` \{#agrag-retrieval-recipes-Recipe-min_score}

```python
min_score: float | None = None
```

##### `agrag.retrieval.recipes.Recipe.reranker` \{#agrag-retrieval-recipes-Recipe-reranker}

```python
reranker: Literal['cross_encoder', 'node_distance'] | None = None
```

#### `agrag.retrieval.recipes.TEXT2CYPHER` \{#agrag-retrieval-recipes-TEXT2CYPHER}

```python
TEXT2CYPHER = Recipe(methods=['text2cypher'], limit=10)
```

#### `agrag.retrieval.recipes.THEMATIC` \{#agrag-retrieval-recipes-THEMATIC}

```python
THEMATIC = Recipe(methods=['community'], limit=5)
```

### `agrag.retrieval.rerank` \{#agrag-retrieval-rerank}

Rerankers that reorder fused search results.

**Modules:**

- [**cross_encoder**](#agrag-retrieval-rerank-cross_encoder) – Cross-encoder reranker using sentence-transformers.
- [**node_distance**](#agrag-retrieval-rerank-node_distance) – Node distance reranker: reorder by graph proximity to seeds.

#### `agrag.retrieval.rerank.cross_encoder` \{#agrag-retrieval-rerank-cross_encoder}

Cross-encoder reranker using sentence-transformers.

**Functions:**

- [**cross_encoder_rerank**](#agrag-retrieval-rerank-cross_encoder-cross_encoder_rerank) – Rerank results using a cross-encoder model.

##### `agrag.retrieval.rerank.cross_encoder.cross_encoder_rerank` \{#agrag-retrieval-rerank-cross_encoder-cross_encoder_rerank}

```python
cross_encoder_rerank(query:str, results:list[SearchResult], *, model:str = 'cross-encoder/ms-marco-MiniLM-L-6-v2', min_score:float | None = None, tracer:Tracer | None = None) -> list[SearchResult]
```

Rerank results using a cross-encoder model.

Requires the `embed-local` extra (sentence-transformers). Scores
(query, text) pairs and reorders by relevance. Drops results scoring
below min_score when set. The model is cached per name (see
\_load_cross_encoder), and the blocking predict() call runs via
asyncio.to_thread so a larger configured model cannot stall the event
loop for other concurrent search() calls. Concurrent first loads of the
same model share one in-flight construction behind a per-model lock, so
only one instance (and one download) occurs.

Without the extra, the results are returned unchanged: the span records
the ImportError and sets `agrag.skipped`, and its status stays UNSET.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text.
- **results** (<code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code>) – The fused results to rerank.
- **model** (<code>str</code>) – The sentence-transformers CrossEncoder model name/path.
  Callers pass RetrievalSettings.cross_encoder_model.
- **min_score** (<code>float | None</code>) – Optional minimum score threshold. Results below this
  are dropped.
- **tracer** (<code>Tracer | None</code>) – Opens the rerank spans. None opens no recorded span.

**Returns:**

- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – Results reranked by cross-encoder score, descending.

#### `agrag.retrieval.rerank.node_distance` \{#agrag-retrieval-rerank-node_distance}

Node distance reranker: reorder by graph proximity to seeds.

**Functions:**

- [**node_distance_rerank**](#agrag-retrieval-rerank-node_distance-node_distance_rerank) – Rerank results by graph proximity to seed entity ids.

##### `agrag.retrieval.rerank.node_distance.node_distance_rerank` \{#agrag-retrieval-rerank-node_distance-node_distance_rerank}

```python
node_distance_rerank(results:list[SearchResult], *, graph_store:GraphStore, seed_ids:list[UUID], tracer:Tracer | None = None) -> list[SearchResult]
```

Rerank results by graph proximity to seed entity ids.

Uses shortest-path distance from each result entity to the
closest seed entity. Entities closer to seeds rank higher. A
ResolvedEntity item is measured by its closest raw member.
Results without an entity item (chunks, relations) are placed
at the end with a high distance penalty.

**Parameters:**

- **results** (<code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code>) – The fused results to rerank.
- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – The graph store for shortest-path queries.
- **seed_ids** (<code>list\[UUID\]</code>) – The seed entity ids to measure distance from. Seeds
  are the query's direct hits, not the whole candidate list:
  a candidate that is its own seed measures distance zero,
  so seeding with every candidate leaves the order unchanged.
- **tracer** (<code>Tracer | None</code>) – Opens the rerank span. None opens no recorded span.

**Returns:**

- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – Results reranked by proximity, closest first.

**Raises:**

- <code>Exception</code> – Any error the graph store raises. A candidate with no
  path to a seed is not an error and ranks with the penalty.

### `agrag.retrieval.resolved_entities` \{#agrag-retrieval-resolved_entities}

Hydration helpers for resolved-entities.

**Functions:**

- [**hydrate_resolved_entities**](#agrag-retrieval-resolved_entities-hydrate_resolved_entities) – Hydrate resolved entities by vector-hit identifiers.
- [**parse_resolved_entity_node**](#agrag-retrieval-resolved_entities-parse_resolved_entity_node) – Parse a graph-store node into a resolved entity when its shape is valid.

#### `agrag.retrieval.resolved_entities.hydrate_resolved_entities` \{#agrag-retrieval-resolved_entities-hydrate_resolved_entities}

```python
hydrate_resolved_entities(graph_store:GraphStore, ids:list[UUID], *, tracer:Tracer | None = None) -> dict[UUID, ResolvedEntity]
```

Hydrate resolved entities by vector-hit identifiers.

**Parameters:**

- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Where the resolved entities live.
- **ids** (<code>list\[UUID\]</code>) – The vector-hit ids to hydrate.
- **tracer** (<code>Tracer | None</code>) – Opens the hydration span. None opens no recorded span.

**Returns:**

- <code>dict\[UUID, [ResolvedEntity](common.md#agrag-common-data_models-resolved_entity-ResolvedEntity)\]</code> – The hydrated resolved entities by id; an empty dict when `ids` is
- <code>dict\[UUID, [ResolvedEntity](common.md#agrag-common-data_models-resolved_entity-ResolvedEntity)\]</code> – empty or nothing parsed.

#### `agrag.retrieval.resolved_entities.parse_resolved_entity_node` \{#agrag-retrieval-resolved_entities-parse_resolved_entity_node}

```python
parse_resolved_entity_node(node:object) -> ResolvedEntity | None
```

Parse a graph-store node into a resolved entity when its shape is valid.

Accepts both the `{"properties": {...}}` mock shape used in tests and a
real Neo4j driver `Node`, which exposes its properties through
`dict(node)` rather than as a plain dict. Flat properties outside
`ResolvedEntity`'s own fields (for example `description`) are routed
into `ResolvedEntity.properties` instead of being dropped by pydantic.

### `agrag.retrieval.retrievers` \{#agrag-retrieval-retrievers}

Retriever implementations for entity, chunk, BFS, and text2cypher search.

**Modules:**

- [**base**](#agrag-retrieval-retrievers-base) – Abstract base class for retrieval methods.
- [**bfs**](#agrag-retrieval-retrievers-bfs) – BFS retriever: graph traversal from seed entity ids.
- [**chunk**](#agrag-retrieval-retrievers-chunk) – Chunk retriever: dense vector search over chunks.
- [**community**](#agrag-retrieval-retrievers-community) – Community retriever: dense vector search over community reports.
- [**entity**](#agrag-retrieval-retrievers-entity) – Entity retriever: dense vector search over entities.
- [**text2cypher**](#agrag-retrieval-retrievers-text2cypher) – Text2Cypher retriever: generate Cypher from natural language.

#### `agrag.retrieval.retrievers.base` \{#agrag-retrieval-retrievers-base}

Abstract base class for retrieval methods.

**Classes:**

- [**Retriever**](#agrag-retrieval-retrievers-base-Retriever) – One retrieval method: given a query, return SearchResults.

##### `agrag.retrieval.retrievers.base.Retriever` \{#agrag-retrieval-retrievers-base-Retriever}

Bases: <code>ABC</code>

One retrieval method: given a query, return SearchResults.

Subclasses own exactly one strategy (dense entity search, chunk
search, BFS expansion). SearchEngine fans a query out to every
Retriever a Recipe names and hands the combined output to Fusion.

**Functions:**

- [**retrieve**](#agrag-retrieval-retrievers-base-Retriever-retrieve) – Run this retrieval method and return hydrated results.

**Attributes:**

- [**name**](#agrag-retrieval-retrievers-base-Retriever-name) (<code>str</code>) –

###### `agrag.retrieval.retrievers.base.Retriever.name` \{#agrag-retrieval-retrievers-base-Retriever-name}

```python
name: str
```

###### `agrag.retrieval.retrievers.base.Retriever.retrieve` \{#agrag-retrieval-retrievers-base-Retriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int = 10) -> list[SearchResult]
```

Run this retrieval method and return hydrated results.

#### `agrag.retrieval.retrievers.bfs` \{#agrag-retrieval-retrievers-bfs}

BFS retriever: graph traversal from seed entity ids.

**Classes:**

- [**BFSRetriever**](#agrag-retrieval-retrievers-bfs-BFSRetriever) – Graph traversal from seed entity ids.

##### `agrag.retrieval.retrievers.bfs.BFSRetriever` \{#agrag-retrieval-retrievers-bfs-BFSRetriever}

```python
BFSRetriever(*, graph_store:GraphStore, settings:RetrievalSettings | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Retriever](#agrag-retrieval-retrievers-base-Retriever)</code>

Graph traversal from seed entity ids.

Takes seed entity ids (from a prior EntityRetriever call, or
supplied directly), runs bfs_expand_query, and hydrates the
returned entities and relations directly.
Degree-capped by RetrievalSettings.traversal_limit.

**Functions:**

- [**retrieve**](#agrag-retrieval-retrievers-bfs-BFSRetriever-retrieve) – Run BFS expansion from seed entity ids.

**Attributes:**

- [**name**](#agrag-retrieval-retrievers-bfs-BFSRetriever-name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – The graph store to traverse.
- **settings** (<code>[RetrievalSettings](#agrag-retrieval-settings-RetrievalSettings) | None</code>) – Retrieval configuration; defaults from
  environment.
- **tracer** (<code>Tracer | None</code>) – Opens the retriever and its children's spans. None
  opens no recorded span.

###### `agrag.retrieval.retrievers.bfs.BFSRetriever.name` \{#agrag-retrieval-retrievers-bfs-BFSRetriever-name}

```python
name = 'bfs'
```

###### `agrag.retrieval.retrievers.bfs.BFSRetriever.retrieve` \{#agrag-retrieval-retrievers-bfs-BFSRetriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int | None = None, seed_ids:list[UUID] | None = None, depth:int | None = None, direction:TraversalDirection = 'both') -> list[SearchResult]
```

Run BFS expansion from seed entity ids.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text (unused for BFS,
  kept for interface consistency).
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Constraints applied to traversal. relation_types
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

- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – SearchResults with entities and relations found via BFS.

#### `agrag.retrieval.retrievers.chunk` \{#agrag-retrieval-retrievers-chunk}

Chunk retriever: dense vector search over chunks.

**Classes:**

- [**ChunkRetriever**](#agrag-retrieval-retrievers-chunk-ChunkRetriever) – Dense chunk search via vector similarity.

##### `agrag.retrieval.retrievers.chunk.ChunkRetriever` \{#agrag-retrieval-retrievers-chunk-ChunkRetriever}

```python
ChunkRetriever(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Retriever](#agrag-retrieval-retrievers-base-Retriever)</code>

Dense chunk search via vector similarity.

Embeds the query, searches via the GraphStore-native or VectorStore
path, then hydrates each hit into a Chunk. The native
path searches the `Chunk` vector index ingestion provisions; the
VectorStore path searches `chunk_collection`.

**Functions:**

- [**retrieve**](#agrag-retrieval-retrievers-chunk-ChunkRetriever-retrieve) – Run chunk search and return hydrated results.

**Attributes:**

- [**name**](#agrag-retrieval-retrievers-chunk-ChunkRetriever-name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Backs chunk search when vector_store is
  absent.
- **embedder** (<code>[Embedder](embedding.md#agrag-embedding-base-Embedder)</code>) – Produces query vectors.
- **vector_store** (<code>[VectorStore](vectordb.md#agrag-vectordb-base-VectorStore) | None</code>) – Optional VectorStore for hybrid search.
- **settings** (<code>[RetrievalSettings](#agrag-retrieval-settings-RetrievalSettings) | None</code>) – Retrieval configuration; defaults from
  environment.
- **tracer** (<code>Tracer | None</code>) – Opens the retriever and its children's spans. None
  opens no recorded span.

###### `agrag.retrieval.retrievers.chunk.ChunkRetriever.name` \{#agrag-retrieval-retrievers-chunk-ChunkRetriever-name}

```python
name = 'chunk'
```

###### `agrag.retrieval.retrievers.chunk.ChunkRetriever.retrieve` \{#agrag-retrieval-retrievers-chunk-ChunkRetriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int | None = None) -> list[SearchResult]
```

Run chunk search and return hydrated results.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Constraints applied to the search.
- **limit** (<code>int | None</code>) – Maximum results. None uses settings.chunk_top_k.
  Zero or negative returns no results without searching.

**Returns:**

- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – Ranked SearchResults with hydrated Chunk items. A child chunk result
- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – carries its parent chunk in `SearchResult.parent`.

#### `agrag.retrieval.retrievers.community` \{#agrag-retrieval-retrievers-community}

Community retriever: dense vector search over community reports.

**Classes:**

- [**CommunityRetriever**](#agrag-retrieval-retrievers-community-CommunityRetriever) – Dense search over community reports, for direct thematic questions.

##### `agrag.retrieval.retrievers.community.CommunityRetriever` \{#agrag-retrieval-retrievers-community-CommunityRetriever}

```python
CommunityRetriever(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Retriever](#agrag-retrieval-retrievers-base-Retriever)</code>

Dense search over community reports, for direct thematic questions.

**Functions:**

- [**retrieve**](#agrag-retrieval-retrievers-community-CommunityRetriever-retrieve) – Run community-report search and return hydrated results.

**Attributes:**

- [**name**](#agrag-retrieval-retrievers-community-CommunityRetriever-name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Where community nodes live.
- **embedder** (<code>[Embedder](embedding.md#agrag-embedding-base-Embedder)</code>) – Produces query vectors.
- **vector_store** (<code>[VectorStore](vectordb.md#agrag-vectordb-base-VectorStore) | None</code>) – Optional VectorStore for hybrid search.
- **settings** (<code>[RetrievalSettings](#agrag-retrieval-settings-RetrievalSettings) | None</code>) – Retrieval configuration; defaults from environment.
- **tracer** (<code>Tracer | None</code>) – Opens the retriever and its children's spans. None
  opens no recorded span.

###### `agrag.retrieval.retrievers.community.CommunityRetriever.name` \{#agrag-retrieval-retrievers-community-CommunityRetriever-name}

```python
name = 'community'
```

###### `agrag.retrieval.retrievers.community.CommunityRetriever.retrieve` \{#agrag-retrieval-retrievers-community-CommunityRetriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int | None = None) -> list[SearchResult]
```

Run community-report search and return hydrated results.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Constraints applied to the search.
- **limit** (<code>int | None</code>) – Maximum results. None uses settings.community_top_k.
  Zero or negative returns no results without searching.

#### `agrag.retrieval.retrievers.entity` \{#agrag-retrieval-retrievers-entity}

Entity retriever: dense vector search over entities.

**Classes:**

- [**EntityRetriever**](#agrag-retrieval-retrievers-entity-EntityRetriever) – Dense entity search via vector similarity.

##### `agrag.retrieval.retrievers.entity.EntityRetriever` \{#agrag-retrieval-retrievers-entity-EntityRetriever}

```python
EntityRetriever(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None, entity_labels:Sequence[str] | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Retriever](#agrag-retrieval-retrievers-base-Retriever)</code>

Dense entity search via vector similarity.

Embeds the query, searches via the GraphStore-native or
VectorStore path, then hydrates every hit from the graph. A hit that
no longer exists in the graph is dropped.

The native path searches one vector index per entity label, so it
needs the labels ingestion provisioned indexes for: the label
filter when the caller sets one, otherwise `entity_labels`.

**Functions:**

- [**retrieve**](#agrag-retrieval-retrievers-entity-EntityRetriever-retrieve) – Run entity search and return hydrated results.

**Attributes:**

- [**name**](#agrag-retrieval-retrievers-entity-EntityRetriever-name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Backs entity search when vector_store is
  absent.
- **embedder** (<code>[Embedder](embedding.md#agrag-embedding-base-Embedder)</code>) – Produces query vectors.
- **vector_store** (<code>[VectorStore](vectordb.md#agrag-vectordb-base-VectorStore) | None</code>) – Optional VectorStore for hybrid search.
- **settings** (<code>[RetrievalSettings](#agrag-retrieval-settings-RetrievalSettings) | None</code>) – Retrieval configuration; defaults from
  environment.
- **entity_labels** (<code>Sequence\[str\] | None</code>) – The schema entity labels native search runs
  against. None uses settings.entity_labels.
- **tracer** (<code>Tracer | None</code>) – Opens the retriever and its children's spans. None
  opens no recorded span.

###### `agrag.retrieval.retrievers.entity.EntityRetriever.name` \{#agrag-retrieval-retrievers-entity-EntityRetriever-name}

```python
name = 'entity'
```

###### `agrag.retrieval.retrievers.entity.EntityRetriever.retrieve` \{#agrag-retrieval-retrievers-entity-EntityRetriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int | None = None) -> list[SearchResult]
```

Run entity search and return hydrated results.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Constraints applied to the search.
- **limit** (<code>int | None</code>) – Maximum results. None uses settings.entity_top_k.
  Zero or negative returns no results without searching.

**Returns:**

- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – Ranked SearchResults with resolved entity ids.

**Raises:**

- <code>ValueError</code> – Native search was selected and neither the
  filter nor the configuration names an entity label.

#### `agrag.retrieval.retrievers.text2cypher` \{#agrag-retrieval-retrievers-text2cypher}

Text2Cypher retriever: generate Cypher from natural language.

**Classes:**

- [**Text2CypherRetriever**](#agrag-retrieval-retrievers-text2cypher-Text2CypherRetriever) – Let the agent ask structured questions via generated Cypher.

**Attributes:**

- [**logger**](#agrag-retrieval-retrievers-text2cypher-logger) –

##### `agrag.retrieval.retrievers.text2cypher.Text2CypherRetriever` \{#agrag-retrieval-retrievers-text2cypher-Text2CypherRetriever}

```python
Text2CypherRetriever(*, graph_store:GraphStore, schema:GraphSchema, settings:RetrievalSettings | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Retriever](#agrag-retrieval-retrievers-base-Retriever)</code>

Let the agent ask structured questions via generated Cypher.

Calls a BAML function to generate a read-only Cypher query
against the graph's declared schema, runs reject_write_cypher as a
safety pre-filter, then bounds the query with a row limit and a
server-side transaction timeout before EXPLAIN and execution. A
query that fails to plan or to execute is regenerated once, carrying
a bounded, sanitized diagnostic of the failure. Rows that carry an
entity id are hydrated from the graph before becoming a
SearchResult; relationship and chunk rows are parsed directly, under
the prompt's own aliases or any alias the model chose instead.
Scalar rows (for example counts or property values) become cited
`QueryValue` results so direct-query answers are not lost.

**Functions:**

- [**retrieve**](#agrag-retrieval-retrievers-text2cypher-Text2CypherRetriever-retrieve) – Generate and execute a Cypher query for the question.

**Attributes:**

- [**name**](#agrag-retrieval-retrievers-text2cypher-Text2CypherRetriever-name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Where the generated query runs.
- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The graph's declared schema. Generation is grounded in
  this schema's labels and relation patterns, so a query the
  graph cannot answer is not generated.
- **settings** (<code>[RetrievalSettings](#agrag-retrieval-settings-RetrievalSettings) | None</code>) – Retrieval configuration; defaults from
  environment.
- **tracer** (<code>Tracer | None</code>) – Opens the generation span and the BAML call spans.

###### `agrag.retrieval.retrievers.text2cypher.Text2CypherRetriever.name` \{#agrag-retrieval-retrievers-text2cypher-Text2CypherRetriever-name}

```python
name = 'text2cypher'
```

###### `agrag.retrieval.retrievers.text2cypher.Text2CypherRetriever.retrieve` \{#agrag-retrieval-retrievers-text2cypher-Text2CypherRetriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int = 10) -> list[SearchResult]
```

Generate and execute a Cypher query for the question.

A query that fails to plan or to execute is regenerated once, with a
bounded, sanitized diagnostic of the first failure attached to the
generation call. A failure at any stage of the second attempt, or a
query rejected by the write gate, returns no results rather than
raising.

**Parameters:**

- **query** (<code>str</code>) – The natural-language question.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Ignored; text2cypher applies its own filters.
- **limit** (<code>int</code>) – Maximum results to return.

**Returns:**

- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – SearchResults from the generated query: entity results
  hydrated from the graph; relation, chunk, and
  scalar rows parsed directly.

##### `agrag.retrieval.retrievers.text2cypher.logger` \{#agrag-retrieval-retrievers-text2cypher-logger}

```python
logger = logging.getLogger(__name__)
```

### `agrag.retrieval.search_engine` \{#agrag-retrieval-search_engine}

Retrieval's public entry point, independent of Graph.

**Classes:**

- [**SearchEngine**](#agrag-retrieval-search_engine-SearchEngine) – Retrieval's public entry point, independent of Graph.

**Attributes:**

- [**logger**](#agrag-retrieval-search_engine-logger) –

#### `agrag.retrieval.search_engine.SearchEngine` \{#agrag-retrieval-search_engine-SearchEngine}

```python
SearchEngine(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None, entity_labels:Sequence[str] | None = None, graph_schema:GraphSchema | None = None, tracer:Tracer | None = None) -> None
```

Retrieval's public entry point, independent of Graph.

Fans a query out to every method a Recipe names, fuses the
results, and optionally reranks them. Constructed from its own
stores; does not depend on a Graph instance existing.

A `tracer` opens the retrieval spans and flows to every
retriever and free function the engine calls. It is *not* pushed
into `graph_store`, `embedder` or `vector_store`: pass the
same tracer to those when you build them, so their adapter spans
nest under these retrieval spans.

**Functions:**

- [**find_entity**](#agrag-retrieval-search_engine-SearchEngine-find_entity) – Resolve a named entity to its top search hit, or None.
- [**list_relationship_types**](#agrag-retrieval-search_engine-SearchEngine-list_relationship_types) – List the relationship types directly attached to an entity.
- [**search**](#agrag-retrieval-search_engine-SearchEngine-search) – Run recipe's methods, fuse, expand, and optionally rerank.
- [**traverse**](#agrag-retrieval-search_engine-SearchEngine-traverse) – Expand one resolved entity into its neighbours.

**Attributes:**

- [**graph_schema**](#agrag-retrieval-search_engine-SearchEngine-graph_schema) (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The schema retrieval is grounded in, GENERIC when none was given.

**Parameters:**

- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Always required; backs entity/chunk search
  when vector_store is absent, and always backs BFS.
- **embedder** (<code>[Embedder](embedding.md#agrag-embedding-base-Embedder)</code>) – Produces query vectors for dense and hybrid
  search.
- **vector_store** (<code>[VectorStore](vectordb.md#agrag-vectordb-base-VectorStore) | None</code>) – Optional. When set, entity, chunk, and
  community search run hybrid_search there instead of
  GraphStore's native search. `Graph.open(vector_store=...)`
  provisions the collections and dual-writes every embedding
  this package ingests, so the two paths see the same data.
  Point it at a store that `Graph.open` provisioned: a
  missing collection makes each method that reads it fail, and
  `search` raises `AllRetrievalMethodsFailedError` when
  every method fails. Collections that exist but hold no
  records return no hits.
- **settings** (<code>[RetrievalSettings](#agrag-retrieval-settings-RetrievalSettings) | None</code>) – Retrieval configuration; defaults from
  environment.
- **entity_labels** (<code>Sequence\[str\] | None</code>) – The entity labels native entity search runs
  against, one vector index each, as provisioned by
  `Graph.open`. Retained as a checked input only: it must
  name exactly the labels graph_schema declares, since the
  schema is what native search and generated Cypher both
  read. Omit it and let the schema drive both. Ignored when
  a vector_store is configured.
- **graph_schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema) | None</code>) – The graph's declared schema, ground truth for
  native entity labels and for generated Cypher. None uses
  `GENERIC`.
- **tracer** (<code>Tracer | None</code>) – Opens the search span and flows to every retriever
  and free function the engine calls. None opens no
  recorded span.

**Raises:**

- <code>ValueError</code> – entity_labels does not name exactly the labels
  graph_schema declares.

##### `agrag.retrieval.search_engine.SearchEngine.find_entity` \{#agrag-retrieval-search_engine-SearchEngine-find_entity}

```python
find_entity(name:str, *, filters:SearchFilters | None = None) -> SearchResult | None
```

Resolve a named entity to its top search hit, or None.

Searches this engine's configured entity_labels by default. A
filters.labels value, when set, overrides which labels are
searched rather than narrowing within entity_labels -- the same
EntityRetriever behavior search()'s own entity search already
relies on.

**Parameters:**

- **name** (<code>str</code>) – The entity name (or description) to resolve.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Scope to resolve within. An entity that exists
  only outside it resolves to None, the same as one that
  does not exist.

**Returns:**

- <code>[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult) | None</code> – The top-ranked SearchResult, or None when nothing matched.

##### `agrag.retrieval.search_engine.SearchEngine.graph_schema` \{#agrag-retrieval-search_engine-SearchEngine-graph_schema}

```python
graph_schema: GraphSchema
```

The schema retrieval is grounded in, GENERIC when none was given.

##### `agrag.retrieval.search_engine.SearchEngine.list_relationship_types` \{#agrag-retrieval-search_engine-SearchEngine-list_relationship_types}

```python
list_relationship_types(seed:SearchResult, *, relation_type_filter:str | None = None, direction:TraversalDirection = 'both', filters:SearchFilters | None = None) -> list[str]
```

List the relationship types directly attached to an entity.

Depth-1 only: it reports what is attached to the seed, never
what lies past it.

**Parameters:**

- **seed** (<code>[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)</code>) – The resolved entity to read attached types from,
  normally from :meth:`find_entity`.
- **relation_type_filter** (<code>str | None</code>) – Only report this type, if present.
- **direction** (<code>TraversalDirection</code>) – Which way to inspect relationships, relative to the
  seed entity.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Scope that limits visible relationship types.

**Returns:**

- <code>list\[str\]</code> – The distinct attached relationship type names.

##### `agrag.retrieval.search_engine.SearchEngine.search` \{#agrag-retrieval-search_engine-SearchEngine-search}

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
- **recipe** (<code>[Recipe](#agrag-retrieval-recipes-Recipe)</code>) – Which methods to run, whether to expand via BFS
  afterward, and which reranker, if any, follows.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Constraints applied identically to every method.

**Returns:**

- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – Up to recipe.limit results, ranked highest-relevance
- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – first.

**Raises:**

- <code>[AllRetrievalMethodsFailedError](#agrag-retrieval-errors-AllRetrievalMethodsFailedError)</code> – Every method the recipe
  names failed. A method failing while others succeed
  is logged and its results are simply absent.
- <code>[UnknownRecipeMethodError](#agrag-retrieval-errors-UnknownRecipeMethodError)</code> – The recipe names one or more
  methods that are not in the retriever registry. A
  misspelled method name is a configuration error and
  is reported instead of silently returning no
  results.

##### `agrag.retrieval.search_engine.SearchEngine.traverse` \{#agrag-retrieval-search_engine-SearchEngine-traverse}

```python
traverse(seed:SearchResult, *, relation_type:str | None = None, direction:TraversalDirection = 'both', depth:int = 1, limit:int = 10, community_expand:bool = False, community_top_k:int = 3, filters:SearchFilters | None = None) -> list[SearchResult]
```

Expand one resolved entity into its neighbours.

**Parameters:**

- **seed** (<code>[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)</code>) – The resolved entity to expand from, normally from
  :meth:`find_entity`.
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
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – Scope for the traversal. Its `relation_types` is
  an allowlist a `relation_type` argument cannot widen;
  its `properties`, `document_ids`, and `labels`
  constrain returned neighbour nodes.

**Returns:**

- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – The neighbouring entities, deduplicated, highest-ranked
- <code>list\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code> – first, with any requested community reports fused in.

**Raises:**

- <code>[ScopeDeniedError](#agrag-retrieval-errors-ScopeDeniedError)</code> – relation_type names a type the caller's
  scope does not permit.

#### `agrag.retrieval.search_engine.logger` \{#agrag-retrieval-search_engine-logger}

```python
logger = logging.getLogger(__name__)
```

### `agrag.retrieval.settings` \{#agrag-retrieval-settings}

Env-backed configuration for retrieval methods and fusion.

**Classes:**

- [**RetrievalSettings**](#agrag-retrieval-settings-RetrievalSettings) – Configuration for retrieval methods and fusion.

#### `agrag.retrieval.settings.RetrievalSettings` \{#agrag-retrieval-settings-RetrievalSettings}

Bases: <code>BaseSettings</code>

Configuration for retrieval methods and fusion.

**Attributes:**

- [**entity_collection**](#agrag-retrieval-settings-RetrievalSettings-entity_collection) (<code>str</code>) – The VectorStore collection name for entity
  search. Only read when a VectorStore is configured on
  SearchEngine; ignored on the GraphStore-native path.
- [**resolved_entity_collection**](#agrag-retrieval-settings-RetrievalSettings-resolved_entity_collection) (<code>str</code>) – The VectorStore collection name for
  resolved-entity search. Same condition as
  entity_collection.
- [**chunk_collection**](#agrag-retrieval-settings-RetrievalSettings-chunk_collection) (<code>str</code>) – The VectorStore collection name for chunk
  search. Same condition as entity_collection.
- [**entity_labels**](#agrag-retrieval-settings-RetrievalSettings-entity_labels) (<code>list\[str\]</code>) – The graph labels native entity search runs
  against, one vector index each. These are the schema's
  entity labels, never a VectorStore collection name. Only
  read when no VectorStore is configured and the caller
  passes no label filter.
- [**node_distance_seed_top_k**](#agrag-retrieval-settings-RetrievalSettings-node_distance_seed_top_k) (<code>int</code>) – How many of the highest-ranked
  entity hits seed the node-distance reranker. Candidates
  are ordered by graph distance to those seeds.
- [**entity_top_k**](#agrag-retrieval-settings-RetrievalSettings-entity_top_k) (<code>int</code>) – Results requested per entity search call.
- [**resolved_entity_top_k**](#agrag-retrieval-settings-RetrievalSettings-resolved_entity_top_k) (<code>int</code>) – Results requested per resolved-entity search
  call.
- [**chunk_top_k**](#agrag-retrieval-settings-RetrievalSettings-chunk_top_k) (<code>int</code>) – Results requested per chunk search call.
- [**hybrid_alpha**](#agrag-retrieval-settings-RetrievalSettings-hybrid_alpha) (<code>float</code>) – Dense-versus-keyword blend for hybrid search,
  0 to 1. Only meaningful on the VectorStore path;
  GraphStore-native search is dense-only and ignores this.
- [**traversal_depth**](#agrag-retrieval-settings-RetrievalSettings-traversal_depth) (<code>int</code>) – Maximum BFS hops from a seed entity.
- [**traversal_limit**](#agrag-retrieval-settings-RetrievalSettings-traversal_limit) (<code>int</code>) – Maximum nodes a BFS expansion can return.
- [**rrf_k**](#agrag-retrieval-settings-RetrievalSettings-rrf_k) (<code>int</code>) – The RRF constant controlling how much rank position
  matters.
- [**reranker_min_score**](#agrag-retrieval-settings-RetrievalSettings-reranker_min_score) (<code>float | None</code>) – Results scoring below this after rerank
  are dropped. None disables the threshold.
- [**text2cypher_timeout_seconds**](#agrag-retrieval-settings-RetrievalSettings-text2cypher_timeout_seconds) (<code>float | None</code>) – Server-side transaction timeout
  applied to generated read queries. The database terminates
  a generated query that runs longer, so a pathological
  query cannot hold server resources indefinitely. None
  uses the server's default timeout.
- [**text2cypher_max_rows**](#agrag-retrieval-settings-RetrievalSettings-text2cypher_max_rows) (<code>int</code>) – Maximum rows a generated read query may
  return. Appended as a LIMIT clause when the generated
  query declares none of its own.
- [**cross_encoder_model**](#agrag-retrieval-settings-RetrievalSettings-cross_encoder_model) (<code>str</code>) – The sentence-transformers CrossEncoder model
  used for cross_encoder reranking. Env:
  RETRIEVAL_CROSS_ENCODER_MODEL.
- [**community_collection**](#agrag-retrieval-settings-RetrievalSettings-community_collection) (<code>str</code>) – The VectorStore collection name for community
  search. Same condition as entity_collection/chunk_collection:
  only read when a VectorStore is configured.
- [**community_top_k**](#agrag-retrieval-settings-RetrievalSettings-community_top_k) (<code>int</code>) – Results requested per community search call when
  the caller passes no explicit limit -- the same role
  entity_top_k/chunk_top_k play for their retrievers. Distinct
  from Recipe.community_top_k (enrichment-budget/reserved-slice
  size): same name, different class, different job.

Env prefix: `RETRIEVAL_`.

##### `agrag.retrieval.settings.RetrievalSettings.chunk_collection` \{#agrag-retrieval-settings-RetrievalSettings-chunk_collection}

```python
chunk_collection: str = 'agrag_chunks'
```

##### `agrag.retrieval.settings.RetrievalSettings.chunk_top_k` \{#agrag-retrieval-settings-RetrievalSettings-chunk_top_k}

```python
chunk_top_k: int = 10
```

##### `agrag.retrieval.settings.RetrievalSettings.community_collection` \{#agrag-retrieval-settings-RetrievalSettings-community_collection}

```python
community_collection: str = 'agrag_communities'
```

##### `agrag.retrieval.settings.RetrievalSettings.community_top_k` \{#agrag-retrieval-settings-RetrievalSettings-community_top_k}

```python
community_top_k: int = 5
```

##### `agrag.retrieval.settings.RetrievalSettings.cross_encoder_model` \{#agrag-retrieval-settings-RetrievalSettings-cross_encoder_model}

```python
cross_encoder_model: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'
```

##### `agrag.retrieval.settings.RetrievalSettings.entity_collection` \{#agrag-retrieval-settings-RetrievalSettings-entity_collection}

```python
entity_collection: str = 'agrag_entities'
```

##### `agrag.retrieval.settings.RetrievalSettings.entity_labels` \{#agrag-retrieval-settings-RetrievalSettings-entity_labels}

```python
entity_labels: list[str] = []
```

##### `agrag.retrieval.settings.RetrievalSettings.entity_top_k` \{#agrag-retrieval-settings-RetrievalSettings-entity_top_k}

```python
entity_top_k: int = 10
```

##### `agrag.retrieval.settings.RetrievalSettings.hybrid_alpha` \{#agrag-retrieval-settings-RetrievalSettings-hybrid_alpha}

```python
hybrid_alpha: float = 0.5
```

##### `agrag.retrieval.settings.RetrievalSettings.model_config` \{#agrag-retrieval-settings-RetrievalSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='RETRIEVAL_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

##### `agrag.retrieval.settings.RetrievalSettings.node_distance_seed_top_k` \{#agrag-retrieval-settings-RetrievalSettings-node_distance_seed_top_k}

```python
node_distance_seed_top_k: int = 3
```

##### `agrag.retrieval.settings.RetrievalSettings.reranker_min_score` \{#agrag-retrieval-settings-RetrievalSettings-reranker_min_score}

```python
reranker_min_score: float | None = None
```

##### `agrag.retrieval.settings.RetrievalSettings.resolved_entity_collection` \{#agrag-retrieval-settings-RetrievalSettings-resolved_entity_collection}

```python
resolved_entity_collection: str = 'agrag_resolved_entities'
```

##### `agrag.retrieval.settings.RetrievalSettings.resolved_entity_top_k` \{#agrag-retrieval-settings-RetrievalSettings-resolved_entity_top_k}

```python
resolved_entity_top_k: int = 10
```

##### `agrag.retrieval.settings.RetrievalSettings.rrf_k` \{#agrag-retrieval-settings-RetrievalSettings-rrf_k}

```python
rrf_k: int = 60
```

##### `agrag.retrieval.settings.RetrievalSettings.text2cypher_max_rows` \{#agrag-retrieval-settings-RetrievalSettings-text2cypher_max_rows}

```python
text2cypher_max_rows: int = 1000
```

##### `agrag.retrieval.settings.RetrievalSettings.text2cypher_timeout_seconds` \{#agrag-retrieval-settings-RetrievalSettings-text2cypher_timeout_seconds}

```python
text2cypher_timeout_seconds: float | None = 10.0
```

##### `agrag.retrieval.settings.RetrievalSettings.traversal_depth` \{#agrag-retrieval-settings-RetrievalSettings-traversal_depth}

```python
traversal_depth: int = 2
```

##### `agrag.retrieval.settings.RetrievalSettings.traversal_limit` \{#agrag-retrieval-settings-RetrievalSettings-traversal_limit}

```python
traversal_limit: int = 50
```

### `agrag.retrieval.tracing` \{#agrag-retrieval-tracing}

Span helpers shared by the retrieval spans.

Every retrieval span that returns a list records the results the same way, so a
trace answers "what came back" without a second lookup.

**Functions:**

- [**filters_json**](#agrag-retrieval-tracing-filters_json) – Return the scope as JSON, an empty scope when `filters` is None.
- [**record_chunks**](#agrag-retrieval-tracing-record_chunks) – Record hydrated chunks as OpenTelemetry-safe attributes.
- [**record_results**](#agrag-retrieval-tracing-record_results) – Write the results onto `span`.
- [**result_text**](#agrag-retrieval-tracing-result_text) – Return the text a result stands for.
- [**retrieval_span**](#agrag-retrieval-tracing-retrieval_span) – Open a `RETRIEVER` span that records the query and the scope.

**Attributes:**

- [**MAX_DOCUMENT_ATTRIBUTES**](#agrag-retrieval-tracing-MAX_DOCUMENT_ATTRIBUTES) –

#### `agrag.retrieval.tracing.MAX_DOCUMENT_ATTRIBUTES` \{#agrag-retrieval-tracing-MAX_DOCUMENT_ATTRIBUTES}

```python
MAX_DOCUMENT_ATTRIBUTES = 20
```

#### `agrag.retrieval.tracing.filters_json` \{#agrag-retrieval-tracing-filters_json}

```python
filters_json(filters:SearchFilters | None) -> str
```

Return the scope as JSON, an empty scope when `filters` is None.

**Parameters:**

- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – The scope a search or retriever ran with, or None.

**Returns:**

- <code>str</code> – The scope as JSON, never None, so a span always records it.

#### `agrag.retrieval.tracing.record_chunks` \{#agrag-retrieval-tracing-record_chunks}

```python
record_chunks(span:Span, chunks:Sequence[Chunk]) -> None
```

Record hydrated chunks as OpenTelemetry-safe attributes.

**Parameters:**

- **span** (<code>Span</code>) – The active retrieval span.
- **chunks** (<code>Sequence\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code>) – Parent chunks attached to child results.

**Returns:**

- <code>None</code> – None.

#### `agrag.retrieval.tracing.record_results` \{#agrag-retrieval-tracing-record_results}

```python
record_results(span:Span, results:Sequence[SearchResult]) -> None
```

Write the results onto `span`.

Full lists go in array attributes, one attribute per array, so the SDK's
per-span attribute limit does not cut a long list. The first
`MAX_DOCUMENT_ATTRIBUTES` results also use the OpenInference
`retrieval.documents.N.*` names, which viewers draw as a retrieval panel.

**Parameters:**

- **span** (<code>Span</code>) – The span that returned `results`. No-op when it is not
  recording.
- **results** (<code>Sequence\[[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)\]</code>) – The results the span's wrapped call returned, in order.

#### `agrag.retrieval.tracing.result_text` \{#agrag-retrieval-tracing-result_text}

```python
result_text(result:SearchResult) -> str
```

Return the text a result stands for.

Entities, resolved entities and communities give their embedding text,
chunks their text, relations `TYPE(source_id, target_id)`, and scalar
query rows JSON.

**Parameters:**

- **result** (<code>[SearchResult](common.md#agrag-common-data_models-search_result-SearchResult)</code>) – The result to render.

**Returns:**

- <code>str</code> – The text the result's item stands for.

#### `agrag.retrieval.tracing.retrieval_span` \{#agrag-retrieval-tracing-retrieval_span}

```python
retrieval_span(tracer:Tracer | None, name:str, *, query:str, filters:SearchFilters | None, attributes:dict[str, Any] | None = None) -> Iterator[Span]
```

Open a `RETRIEVER` span that records the query and the scope.

Use it for retriever spans and for root spans that return
`SearchResult`s. The caller calls `record_results` on the yielded span
before it exits.

**Parameters:**

- **tracer** (<code>Tracer | None</code>) – The caller's tracer, or None for a no-op tracer.
- **name** (<code>str</code>) – The span name, in the `agrag.retrieval.*` namespace.
- **query** (<code>str</code>) – The natural-language query, or the seed's text.
- **filters** (<code>[SearchFilters](#agrag-retrieval-filters-SearchFilters) | None</code>) – The scope the wrapped call runs under, always recorded.
- **attributes** (<code>dict\[str, Any\] | None</code>) – Extra cheap attributes known before the call starts.

**Yields:**

- <code>Span</code> – The open span, for `record_results` and any later attributes.
