---
title: agrag.common.data_models.vector_record.VectorHit
sidebar_label: VectorHit
---

# `agrag.common.data_models.vector_record.VectorHit` \{#agrag-common-data_models-vector_record-VectorHit}

Bases: <code>BaseModel</code>

One search result: a matched id, its score, and its stored payload.

Returned by both `VectorStore.search`/`hybrid_search` and
`GraphStore.vector_search`, so a caller cannot tell which store produced
a given hit.

**Attributes:**

- [**id**](#agrag-common-data_models-vector_record-VectorHit-id) (<code>UUID</code>) – The id of the matched record.
- [**score**](#agrag-common-data_models-vector_record-VectorHit-score) (<code>float</code>) – The match score. Higher means a closer match, regardless of
  which distance metric the collection uses.
- [**payload**](#agrag-common-data_models-vector_record-VectorHit-payload) (<code>dict\[str, Any\]</code>) – The payload stored with the matched record.

## `id` \{#agrag-common-data_models-vector_record-VectorHit-id}

```python
id: UUID
```

## `payload` \{#agrag-common-data_models-vector_record-VectorHit-payload}

```python
payload: dict[str, Any]
```

## `score` \{#agrag-common-data_models-vector_record-VectorHit-score}

```python
score: float
```
