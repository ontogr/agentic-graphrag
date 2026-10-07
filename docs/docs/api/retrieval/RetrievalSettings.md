---
title: agrag.retrieval.RetrievalSettings
sidebar_label: RetrievalSettings
---

# `agrag.retrieval.RetrievalSettings` \{#agrag-retrieval-RetrievalSettings}

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

## `chunk_collection` \{#agrag-retrieval-RetrievalSettings-chunk_collection}

```python
chunk_collection: str = 'agrag_chunks'
```

## `chunk_top_k` \{#agrag-retrieval-RetrievalSettings-chunk_top_k}

```python
chunk_top_k: int = 10
```

## `community_collection` \{#agrag-retrieval-RetrievalSettings-community_collection}

```python
community_collection: str = 'agrag_communities'
```

## `community_top_k` \{#agrag-retrieval-RetrievalSettings-community_top_k}

```python
community_top_k: int = 5
```

## `cross_encoder_model` \{#agrag-retrieval-RetrievalSettings-cross_encoder_model}

```python
cross_encoder_model: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'
```

## `entity_collection` \{#agrag-retrieval-RetrievalSettings-entity_collection}

```python
entity_collection: str = 'agrag_entities'
```

## `entity_labels` \{#agrag-retrieval-RetrievalSettings-entity_labels}

```python
entity_labels: list[str] = []
```

## `entity_top_k` \{#agrag-retrieval-RetrievalSettings-entity_top_k}

```python
entity_top_k: int = 10
```

## `hybrid_alpha` \{#agrag-retrieval-RetrievalSettings-hybrid_alpha}

```python
hybrid_alpha: float = 0.5
```

## `model_config` \{#agrag-retrieval-RetrievalSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='RETRIEVAL_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

## `node_distance_seed_top_k` \{#agrag-retrieval-RetrievalSettings-node_distance_seed_top_k}

```python
node_distance_seed_top_k: int = 3
```

## `reranker_min_score` \{#agrag-retrieval-RetrievalSettings-reranker_min_score}

```python
reranker_min_score: float | None = None
```

## `resolved_entity_collection` \{#agrag-retrieval-RetrievalSettings-resolved_entity_collection}

```python
resolved_entity_collection: str = 'agrag_resolved_entities'
```

## `resolved_entity_top_k` \{#agrag-retrieval-RetrievalSettings-resolved_entity_top_k}

```python
resolved_entity_top_k: int = 10
```

## `rrf_k` \{#agrag-retrieval-RetrievalSettings-rrf_k}

```python
rrf_k: int = 60
```

## `text2cypher_max_rows` \{#agrag-retrieval-RetrievalSettings-text2cypher_max_rows}

```python
text2cypher_max_rows: int = 1000
```

## `text2cypher_timeout_seconds` \{#agrag-retrieval-RetrievalSettings-text2cypher_timeout_seconds}

```python
text2cypher_timeout_seconds: float | None = 10.0
```

## `traversal_depth` \{#agrag-retrieval-RetrievalSettings-traversal_depth}

```python
traversal_depth: int = 2
```

## `traversal_limit` \{#agrag-retrieval-RetrievalSettings-traversal_limit}

```python
traversal_limit: int = 50
```
