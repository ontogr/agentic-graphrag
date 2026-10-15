---
title: agrag.retrieval.settings.RetrievalSettings
sidebar_label: RetrievalSettings
---

# `agrag.retrieval.settings.RetrievalSettings` \{#agrag-retrieval-settings-RetrievalSettings}

Bases: <code>BaseSettings</code>

Configuration for retrieval methods and fusion.

**Attributes:**

- [**entity_labels**](#agrag-retrieval-settings-RetrievalSettings-entity_labels) (<code>list\[str\]</code>) – The graph labels native entity search runs
  against, one vector index each. These are the schema's
  entity labels. Only read when the caller passes no label
  filter.
- [**node_distance_seed_top_k**](#agrag-retrieval-settings-RetrievalSettings-node_distance_seed_top_k) (<code>int</code>) – How many of the highest-ranked
  entity hits seed the node-distance reranker. Candidates
  are ordered by graph distance to those seeds.
- [**entity_top_k**](#agrag-retrieval-settings-RetrievalSettings-entity_top_k) (<code>int</code>) – Results requested per entity search call.
- [**resolved_entity_top_k**](#agrag-retrieval-settings-RetrievalSettings-resolved_entity_top_k) (<code>int</code>) – Results requested per resolved-entity search
  call.
- [**chunk_top_k**](#agrag-retrieval-settings-RetrievalSettings-chunk_top_k) (<code>int</code>) – Results requested per chunk search call.
- [**traversal_depth**](#agrag-retrieval-settings-RetrievalSettings-traversal_depth) (<code>int</code>) – Maximum BFS hops from a seed entity.
- [**traversal_limit**](#agrag-retrieval-settings-RetrievalSettings-traversal_limit) (<code>int</code>) – Maximum nodes a BFS expansion can return.
- [**rrf_k**](#agrag-retrieval-settings-RetrievalSettings-rrf_k) (<code>int</code>) – The RRF constant controlling how much rank position
  matters.
- [**reranker_min_score**](#agrag-retrieval-settings-RetrievalSettings-reranker_min_score) (<code>float | None</code>) – Results scoring below this after rerank
  are dropped. None disables the threshold.
- [**cross_encoder_model**](#agrag-retrieval-settings-RetrievalSettings-cross_encoder_model) (<code>str</code>) – The sentence-transformers CrossEncoder model
  used for cross_encoder reranking. Env:
  RETRIEVAL_CROSS_ENCODER_MODEL.
- [**community_top_k**](#agrag-retrieval-settings-RetrievalSettings-community_top_k) (<code>int</code>) – Results requested per community search call when
  the caller passes no explicit limit. It plays the same role
  entity_top_k and chunk_top_k play for their retrievers. It is
  distinct from Recipe.community_top_k (enrichment budget and
  reserved slice size). Same name, different class, different job.

Env prefix: `RETRIEVAL_`.

## `chunk_top_k` \{#agrag-retrieval-settings-RetrievalSettings-chunk_top_k}

```python
chunk_top_k: int = 10
```

## `community_top_k` \{#agrag-retrieval-settings-RetrievalSettings-community_top_k}

```python
community_top_k: int = 5
```

## `cross_encoder_model` \{#agrag-retrieval-settings-RetrievalSettings-cross_encoder_model}

```python
cross_encoder_model: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'
```

## `entity_labels` \{#agrag-retrieval-settings-RetrievalSettings-entity_labels}

```python
entity_labels: list[str] = []
```

## `entity_top_k` \{#agrag-retrieval-settings-RetrievalSettings-entity_top_k}

```python
entity_top_k: int = 10
```

## `model_config` \{#agrag-retrieval-settings-RetrievalSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='RETRIEVAL_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

## `node_distance_seed_top_k` \{#agrag-retrieval-settings-RetrievalSettings-node_distance_seed_top_k}

```python
node_distance_seed_top_k: int = 3
```

## `reranker_min_score` \{#agrag-retrieval-settings-RetrievalSettings-reranker_min_score}

```python
reranker_min_score: float | None = None
```

## `resolved_entity_top_k` \{#agrag-retrieval-settings-RetrievalSettings-resolved_entity_top_k}

```python
resolved_entity_top_k: int = 10
```

## `rrf_k` \{#agrag-retrieval-settings-RetrievalSettings-rrf_k}

```python
rrf_k: int = 60
```

## `traversal_depth` \{#agrag-retrieval-settings-RetrievalSettings-traversal_depth}

```python
traversal_depth: int = 2
```

## `traversal_limit` \{#agrag-retrieval-settings-RetrievalSettings-traversal_limit}

```python
traversal_limit: int = 50
```
