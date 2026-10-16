---
title: agrag.retrieval.recipes.Recipe
sidebar_label: Recipe
---

# `agrag.retrieval.recipes.Recipe` \{#agrag-retrieval-recipes-Recipe}

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

## `bfs` \{#agrag-retrieval-recipes-Recipe-bfs}

```python
bfs: bool = False
```

## `bfs_depth` \{#agrag-retrieval-recipes-Recipe-bfs_depth}

```python
bfs_depth: int | None = None
```

## `community_expand` \{#agrag-retrieval-recipes-Recipe-community_expand}

```python
community_expand: bool = False
```

## `community_top_k` \{#agrag-retrieval-recipes-Recipe-community_top_k}

```python
community_top_k: int = 3
```

## `limit` \{#agrag-retrieval-recipes-Recipe-limit}

```python
limit: int = 10
```

## `methods` \{#agrag-retrieval-recipes-Recipe-methods}

```python
methods: list[str]
```

## `min_score` \{#agrag-retrieval-recipes-Recipe-min_score}

```python
min_score: float | None = None
```

## `reranker` \{#agrag-retrieval-recipes-Recipe-reranker}

```python
reranker: Literal['cross_encoder', 'node_distance'] | None = None
```
