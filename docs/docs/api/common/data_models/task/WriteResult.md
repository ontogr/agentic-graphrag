---
title: agrag.common.data_models.task.WriteResult
sidebar_label: WriteResult
---

# `agrag.common.data_models.task.WriteResult` \{#agrag-common-data_models-task-WriteResult}

Bases: <code>BaseModel</code>

Base outcome of a conversation history write.

**Attributes:**

- [**recorded**](#agrag-common-data_models-task-WriteResult-recorded) (<code>bool</code>) – Whether the write is in effect. A retry with the same request
  id reports the stored outcome of the first call.
- [**error**](#agrag-common-data_models-task-WriteResult-error) (<code>[WriteErrorCode](WriteErrorCode.md) | None</code>) – The fixed error code when `recorded` is false.

## `error` \{#agrag-common-data_models-task-WriteResult-error}

```python
error: WriteErrorCode | None = None
```

## `model_config` \{#agrag-common-data_models-task-WriteResult-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `recorded` \{#agrag-common-data_models-task-WriteResult-recorded}

```python
recorded: bool
```
