---
title: agrag.common.data_models.VectorRecord
sidebar_label: VectorRecord
---

# `agrag.common.data_models.VectorRecord` \{#agrag-common-data_models-VectorRecord}

Bases: <code>BaseModel</code>

One vector and its payload, ready to write to a collection or index.

The collection or index name is a call argument on the store, not a field
here, so one record type can target any collection.

**Attributes:**

- [**id**](#agrag-common-data_models-VectorRecord-id) (<code>UUID</code>) – The record id. Callers set this to the id of the domain object the
  vector represents.
- [**vector**](#agrag-common-data_models-VectorRecord-vector) (<code>list\[float\]</code>) – The dense embedding.
- [**payload**](#agrag-common-data_models-VectorRecord-payload) (<code>dict\[str, Any\]</code>) – Fields stored alongside the vector, such as the source text or
  a chunk id. Read back unchanged by `search`/`hybrid_search`.

## `id` \{#agrag-common-data_models-VectorRecord-id}

```python
id: UUID
```

## `payload` \{#agrag-common-data_models-VectorRecord-payload}

```python
payload: dict[str, Any]
```

## `vector` \{#agrag-common-data_models-VectorRecord-vector}

```python
vector: list[float]
```
