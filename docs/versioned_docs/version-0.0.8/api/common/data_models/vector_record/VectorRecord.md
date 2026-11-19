---
title: agrag.common.data_models.vector_record.VectorRecord
sidebar_label: VectorRecord
---

# `agrag.common.data_models.vector_record.VectorRecord` \{#agrag-common-data_models-vector_record-VectorRecord}

Bases: <code>BaseModel</code>

An embedding with searchable labels and its exact embedding input.

**Attributes:**

- [**id**](#agrag-common-data_models-vector_record-VectorRecord-id) (<code>UUID</code>) – The graph node id.
- [**vector**](#agrag-common-data_models-vector_record-VectorRecord-vector) (<code>list\[float\]</code>) – Dense embedding values.
- [**labels**](#agrag-common-data_models-vector_record-VectorRecord-labels) (<code>list\[str\]</code>) – Schema label and ancestors, or one system kind label.
- [**text**](#agrag-common-data_models-vector_record-VectorRecord-text) (<code>str</code>) – The exact embedding input, also used for lexical search.

## `id` \{#agrag-common-data_models-vector_record-VectorRecord-id}

```python
id: UUID
```

## `labels` \{#agrag-common-data_models-vector_record-VectorRecord-labels}

```python
labels: list[str]
```

## `text` \{#agrag-common-data_models-vector_record-VectorRecord-text}

```python
text: str
```

## `vector` \{#agrag-common-data_models-vector_record-VectorRecord-vector}

```python
vector: list[float]
```
