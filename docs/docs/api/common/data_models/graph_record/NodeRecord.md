---
title: agrag.common.data_models.graph_record.NodeRecord
sidebar_label: NodeRecord
---

# `agrag.common.data_models.graph_record.NodeRecord` \{#agrag-common-data_models-graph_record-NodeRecord}

Bases: <code>BaseModel</code>

One graph node, ready to write.

**Attributes:**

- [**id**](#agrag-common-data_models-graph_record-NodeRecord-id) (<code>UUID</code>) – The node id.
- [**labels**](#agrag-common-data_models-graph_record-NodeRecord-labels) (<code>list\[str\]</code>) – The node labels. A node carries every label listed here.
  `GraphStore.upsert_nodes` groups records by their full label set
  within a batch, since Cypher requires labels to be literal in the
  query rather than a runtime parameter.
- [**properties**](#agrag-common-data_models-graph_record-NodeRecord-properties) (<code>dict\[str, Any\]</code>) – The node's properties, including an embedding vector under
  whatever key `GraphStore.ensure_vector_index` was configured
  with, if native vector search is in use.

**Functions:**

- [**reject_pending_tag**](#agrag-common-data_models-graph_record-NodeRecord-reject_pending_tag) – Reject the job-owned tag in external graph records.

## `id` \{#agrag-common-data_models-graph_record-NodeRecord-id}

```python
id: UUID
```

## `labels` \{#agrag-common-data_models-graph_record-NodeRecord-labels}

```python
labels: list[str] = Field(min_length=1)
```

## `properties` \{#agrag-common-data_models-graph_record-NodeRecord-properties}

```python
properties: dict[str, Any]
```

## `reject_pending_tag` \{#agrag-common-data_models-graph_record-NodeRecord-reject_pending_tag}

```python
reject_pending_tag(properties:dict[str, Any]) -> dict[str, Any]
```

Reject the job-owned tag in external graph records.
