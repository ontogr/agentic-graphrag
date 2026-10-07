---
title: agrag.common.data_models.RelationRecord
sidebar_label: RelationRecord
---

# `agrag.common.data_models.RelationRecord` \{#agrag-common-data_models-RelationRecord}

Bases: <code>BaseModel</code>

One graph relationship, ready to write.

**Attributes:**

- [**id**](#agrag-common-data_models-RelationRecord-id) (<code>UUID</code>) – The relationship id.
- [**type**](#agrag-common-data_models-RelationRecord-type) (<code>str</code>) – The relationship type.
- [**start_id**](#agrag-common-data_models-RelationRecord-start_id) (<code>UUID</code>) – The id of the start node.
- [**end_id**](#agrag-common-data_models-RelationRecord-end_id) (<code>UUID</code>) – The id of the end node.
- [**properties**](#agrag-common-data_models-RelationRecord-properties) (<code>dict\[str, Any\]</code>) – The relationship's properties.

**Functions:**

- [**reject_pending_tag**](#agrag-common-data_models-RelationRecord-reject_pending_tag) – Reject the job-owned tag in external graph records.

## `end_id` \{#agrag-common-data_models-RelationRecord-end_id}

```python
end_id: UUID
```

## `id` \{#agrag-common-data_models-RelationRecord-id}

```python
id: UUID
```

## `properties` \{#agrag-common-data_models-RelationRecord-properties}

```python
properties: dict[str, Any]
```

## `reject_pending_tag` \{#agrag-common-data_models-RelationRecord-reject_pending_tag}

```python
reject_pending_tag(properties:dict[str, Any]) -> dict[str, Any]
```

Reject the job-owned tag in external graph records.

## `start_id` \{#agrag-common-data_models-RelationRecord-start_id}

```python
start_id: UUID
```

## `type` \{#agrag-common-data_models-RelationRecord-type}

```python
type: str
```
