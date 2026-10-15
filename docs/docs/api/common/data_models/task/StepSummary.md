---
title: agrag.common.data_models.task.StepSummary
sidebar_label: StepSummary
---

# `agrag.common.data_models.task.StepSummary` \{#agrag-common-data_models-task-StepSummary}

Bases: <code>BaseModel</code>

The fields of a step that a resume view shows.

**Attributes:**

- [**name**](#agrag-common-data_models-task-StepSummary-name) (<code>str</code>) – Step name.
- [**kind**](#agrag-common-data_models-task-StepSummary-kind) (<code>[StepKind](StepKind.md)</code>) – Broad category of the step.
- [**state**](#agrag-common-data_models-task-StepSummary-state) (<code>[StepState](StepState.md)</code>) – Current state.
- [**result_event_seq**](#agrag-common-data_models-task-StepSummary-result_event_seq) (<code>int | None</code>) – Sequence number of the result event, or None.

## `kind` \{#agrag-common-data_models-task-StepSummary-kind}

```python
kind: StepKind
```

## `model_config` \{#agrag-common-data_models-task-StepSummary-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `name` \{#agrag-common-data_models-task-StepSummary-name}

```python
name: str
```

## `result_event_seq` \{#agrag-common-data_models-task-StepSummary-result_event_seq}

```python
result_event_seq: int | None
```

## `state` \{#agrag-common-data_models-task-StepSummary-state}

```python
state: StepState
```
