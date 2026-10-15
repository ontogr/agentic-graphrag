---
title: agrag.common.data_models.task.RecordEventResult
sidebar_label: RecordEventResult
---

# `agrag.common.data_models.task.RecordEventResult` \{#agrag-common-data_models-task-RecordEventResult}

Bases: <code>[WriteResult](WriteResult.md)</code>

The outcome of appending one event.

**Attributes:**

- [**event**](#agrag-common-data_models-task-RecordEventResult-event) (<code>[Event](Event.md) | None</code>) – The appended event when `recorded` is true.

## `error` \{#agrag-common-data_models-task-RecordEventResult-error}

```python
error: MemoryErrorCode | None = None
```

## `event` \{#agrag-common-data_models-task-RecordEventResult-event}

```python
event: Event | None = None
```

## `model_config` \{#agrag-common-data_models-task-RecordEventResult-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `recorded` \{#agrag-common-data_models-task-RecordEventResult-recorded}

```python
recorded: bool
```
