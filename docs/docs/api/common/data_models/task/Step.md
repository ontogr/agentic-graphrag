---
title: agrag.common.data_models.task.Step
sidebar_label: Step
---

# `agrag.common.data_models.task.Step` \{#agrag-common-data_models-task-Step}

Bases: <code>BaseModel</code>

A named step of a task with an explicit state.

**Attributes:**

- [**id**](#agrag-common-data_models-task-Step-id) (<code>UUID</code>) – Identifier derived from the task id and the step name.
- [**task_id**](#agrag-common-data_models-task-Step-task_id) (<code>UUID</code>) – The task the step belongs to.
- [**name**](#agrag-common-data_models-task-Step-name) (<code>str</code>) – Step name, unique within the task.
- [**kind**](#agrag-common-data_models-task-Step-kind) (<code>[StepKind](StepKind.md)</code>) – Broad category of the step.
- [**state**](#agrag-common-data_models-task-Step-state) (<code>[StepState](StepState.md)</code>) – Current state.
- [**result_event_seq**](#agrag-common-data_models-task-Step-result_event_seq) (<code>int | None</code>) – Sequence number of the event that holds the step's
  result, or None.
- [**updated_seq**](#agrag-common-data_models-task-Step-updated_seq) (<code>int</code>) – The task's event sequence number when the step was last
  set.

## `id` \{#agrag-common-data_models-task-Step-id}

```python
id: UUID
```

## `kind` \{#agrag-common-data_models-task-Step-kind}

```python
kind: StepKind
```

## `model_config` \{#agrag-common-data_models-task-Step-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `name` \{#agrag-common-data_models-task-Step-name}

```python
name: str
```

## `result_event_seq` \{#agrag-common-data_models-task-Step-result_event_seq}

```python
result_event_seq: int | None
```

## `state` \{#agrag-common-data_models-task-Step-state}

```python
state: StepState
```

## `task_id` \{#agrag-common-data_models-task-Step-task_id}

```python
task_id: UUID
```

## `updated_seq` \{#agrag-common-data_models-task-Step-updated_seq}

```python
updated_seq: int
```
