---
title: agrag.common.data_models.data_point.DataPoint
sidebar_label: DataPoint
---

# `agrag.common.data_models.data_point.DataPoint` \{#agrag-common-data_models-data_point-DataPoint}

Bases: <code>BaseModel</code>

A graph node with a fixed id and free metadata.

**Attributes:**

- [**id**](#agrag-common-data_models-data_point-DataPoint-id) (<code>UUID</code>) – The node id. Each subclass defines its own rule to compute this id.
- [**created_at**](#agrag-common-data_models-data_point-DataPoint-created_at) (<code>datetime</code>) – The time the system created this node. Defaults to the current time.
- [**metadata**](#agrag-common-data_models-data_point-DataPoint-metadata) (<code>dict\[str, Any\]</code>) – Extra data about the node. Add an `index_fields` key to list
  which fields the store must index for filters.

## `created_at` \{#agrag-common-data_models-data_point-DataPoint-created_at}

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

## `id` \{#agrag-common-data_models-data_point-DataPoint-id}

```python
id: UUID
```

## `metadata` \{#agrag-common-data_models-data_point-DataPoint-metadata}

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```
