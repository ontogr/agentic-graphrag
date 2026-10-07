---
title: agrag.common.data_models.graph_record.UpsertFailure
sidebar_label: UpsertFailure
---

# `agrag.common.data_models.graph_record.UpsertFailure` \{#agrag-common-data_models-graph_record-UpsertFailure}

Bases: <code>BaseModel</code>

One record that failed to write within a bulk upsert call.

**Attributes:**

- [**id**](#agrag-common-data_models-graph_record-UpsertFailure-id) (<code>str</code>) – The failed record's own id, as a string (matches the id already
  sent to the backend, not necessarily parseable back to UUID for
  every future backend).
- [**error_type**](#agrag-common-data_models-graph_record-UpsertFailure-error_type) (<code>str</code>) – The backend exception class name or GraphStore failure label.
- [**error_message**](#agrag-common-data_models-graph_record-UpsertFailure-error_message) (<code>str</code>) – The backend exception message or failure description.

## `error_message` \{#agrag-common-data_models-graph_record-UpsertFailure-error_message}

```python
error_message: str
```

## `error_type` \{#agrag-common-data_models-graph_record-UpsertFailure-error_type}

```python
error_type: str
```

## `id` \{#agrag-common-data_models-graph_record-UpsertFailure-id}

```python
id: str
```
