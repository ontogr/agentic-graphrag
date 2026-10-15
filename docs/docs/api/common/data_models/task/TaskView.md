---
title: agrag.common.data_models.task.TaskView
sidebar_label: TaskView
---

# `agrag.common.data_models.task.TaskView` \{#agrag-common-data_models-task-TaskView}

Bases: <code>BaseModel</code>

A bounded resume view of one task. It never includes event bodies.

**Attributes:**

- [**task_name**](#agrag-common-data_models-task-TaskView-task_name) (<code>str</code>) – Task name.
- [**goal**](#agrag-common-data_models-task-TaskView-goal) (<code>str</code>) – The task goal.
- [**status**](#agrag-common-data_models-task-TaskView-status) (<code>[TaskStatus](TaskStatus.md)</code>) – Lifecycle state.
- [**last_event_seq**](#agrag-common-data_models-task-TaskView-last_event_seq) (<code>int</code>) – The sequence number of the last event, or 0.
- [**steps**](#agrag-common-data_models-task-TaskView-steps) (<code>dict\[[StepState](StepState.md), list\[[StepSummary](StepSummary.md)\]\]</code>) – Shown steps grouped by state. Every state is a key, in the
  order of `STEP_STATE_ORDER`. The shown steps are capped across
  all states.
- [**step_counts**](#agrag-common-data_models-task-TaskView-step_counts) (<code>dict\[[StepState](StepState.md), int\]</code>) – Number of steps in each state, including steps that the
  cap hides. Every state is a key.
- [**steps_truncated**](#agrag-common-data_models-task-TaskView-steps_truncated) (<code>bool</code>) – Whether some steps are hidden by the cap.

## `goal` \{#agrag-common-data_models-task-TaskView-goal}

```python
goal: str
```

## `last_event_seq` \{#agrag-common-data_models-task-TaskView-last_event_seq}

```python
last_event_seq: int
```

## `model_config` \{#agrag-common-data_models-task-TaskView-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `status` \{#agrag-common-data_models-task-TaskView-status}

```python
status: TaskStatus
```

## `step_counts` \{#agrag-common-data_models-task-TaskView-step_counts}

```python
step_counts: dict[StepState, int]
```

## `steps` \{#agrag-common-data_models-task-TaskView-steps}

```python
steps: dict[StepState, list[StepSummary]]
```

## `steps_truncated` \{#agrag-common-data_models-task-TaskView-steps_truncated}

```python
steps_truncated: bool
```

## `task_name` \{#agrag-common-data_models-task-TaskView-task_name}

```python
task_name: str
```
