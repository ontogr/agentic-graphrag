---
title: agrag.common.data_models.search_result.SearchResult
sidebar_label: SearchResult
---

# `agrag.common.data_models.search_result.SearchResult` \{#agrag-common-data_models-search_result-SearchResult}

Bases: <code>BaseModel</code>

One retrieved item, tagged with where it came from.

**Attributes:**

- [**item**](#agrag-common-data_models-search_result-SearchResult-item) (<code>Union\[[Entity](../entity/Entity-ref.md), [ResolvedEntity](../resolved_entity/ResolvedEntity.md), [Relation](../relation/Relation-ref.md), [Chunk](../chunk/Chunk-ref.md), [Community](../community/Community-ref.md), [QueryValue](../query_value/QueryValue.md)\]</code>) – The retrieved Entity, ResolvedEntity, Relation, Chunk, or
  Community, or scalar query value, already resolved through any
  merged_into chain.
- [**score**](#agrag-common-data_models-search_result-SearchResult-score) (<code>float</code>) – The method's own relevance score. Not comparable
  across methods until Fusion normalizes it.
- [**method**](#agrag-common-data_models-search_result-SearchResult-method) (<code>str</code>) – The name of the retrieval method that produced
  this result.
- [**parent**](#agrag-common-data_models-search_result-SearchResult-parent) (<code>[Chunk](../chunk/Chunk-ref.md) | None</code>) – The parent chunk of a child chunk result, so a caller can show the
  larger passage. `None` for every other result.

## `identity_key` \{#agrag-common-data_models-search_result-SearchResult-identity_key}

```python
identity_key: tuple[str, UUID]
```

Return the (type, id) key Fusion deduplicates on.

**Raises:**

- <code>ValueError</code> – The item has no id, so it cannot be
  deduplicated.

## `item` \{#agrag-common-data_models-search_result-SearchResult-item}

```python
item: Union[Entity, ResolvedEntity, Relation, Chunk, Community, QueryValue]
```

## `method` \{#agrag-common-data_models-search_result-SearchResult-method}

```python
method: str
```

## `parent` \{#agrag-common-data_models-search_result-SearchResult-parent}

```python
parent: Chunk | None = None
```

## `score` \{#agrag-common-data_models-search_result-SearchResult-score}

```python
score: float
```
