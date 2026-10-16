---
title: agrag.common.data_models.task.SetStepResult
sidebar_label: SetStepResult
---

# `agrag.common.data_models.task.SetStepResult` \{#agrag-common-data_models-task-SetStepResult}

Bases: <code>[WriteResult](WriteResult.md)</code>

The outcome of creating or updating a step.

**Attributes:**

- [**step**](#agrag-common-data_models-task-SetStepResult-step) (<code>[Step](Step.md) | None</code>) – The step when `recorded` is true.

## `error` \{#agrag-common-data_models-task-SetStepResult-error}

```python
error: MemoryErrorCode | None = None
```

## `model_config` \{#agrag-common-data_models-task-SetStepResult-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `recorded` \{#agrag-common-data_models-task-SetStepResult-recorded}

```python
recorded: bool
```

## `step` \{#agrag-common-data_models-task-SetStepResult-step}

```python
step: Step | None = None
```
