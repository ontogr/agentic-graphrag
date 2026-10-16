---
title: agrag.common.data_models.graph_record.UpsertResult
sidebar_label: UpsertResult
---

# `agrag.common.data_models.graph_record.UpsertResult` \{#agrag-common-data_models-graph_record-UpsertResult}

Bases: <code>BaseModel</code>

Outcome of a bulk `upsert_nodes`/`upsert_relations` call.

**Attributes:**

- [**written**](#agrag-common-data_models-graph_record-UpsertResult-written) (<code>int</code>) – How many records were written successfully.
- [**failures**](#agrag-common-data_models-graph_record-UpsertResult-failures) (<code>list\[[UpsertFailure](UpsertFailure.md)\]</code>) – Records that failed, isolated from the rest of the call.
  Empty when every record wrote successfully.

## `failures` \{#agrag-common-data_models-graph_record-UpsertResult-failures}

```python
failures: list[UpsertFailure] = Field(default_factory=list)
```

## `written` \{#agrag-common-data_models-graph_record-UpsertResult-written}

```python
written: int = 0
```
