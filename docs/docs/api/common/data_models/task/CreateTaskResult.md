---
title: agrag.common.data_models.task.CreateTaskResult
sidebar_label: CreateTaskResult
---

# `agrag.common.data_models.task.CreateTaskResult` \{#agrag-common-data_models-task-CreateTaskResult}

Bases: <code>[WriteResult](WriteResult.md)</code>

The outcome of creating or reusing a task.

**Attributes:**

- [**task**](#agrag-common-data_models-task-CreateTaskResult-task) (<code>[Task](Task-ref.md) | None</code>) – The task when `recorded` is true.

## `error` \{#agrag-common-data_models-task-CreateTaskResult-error}

```python
error: MemoryErrorCode | None = None
```

## `model_config` \{#agrag-common-data_models-task-CreateTaskResult-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `recorded` \{#agrag-common-data_models-task-CreateTaskResult-recorded}

```python
recorded: bool
```

## `task` \{#agrag-common-data_models-task-CreateTaskResult-task}

```python
task: Task | None = None
```
