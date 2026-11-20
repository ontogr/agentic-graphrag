---
title: agrag.common.data_models.task.TaskLookup
sidebar_label: TaskLookup
---

# `agrag.common.data_models.task.TaskLookup` \{#agrag-common-data_models-task-TaskLookup}

Bases: <code>BaseModel</code>

The result of reading a task view by name.

**Attributes:**

- [**found**](#agrag-common-data_models-task-TaskLookup-found) (<code>bool</code>) – Whether a task with that name exists in the project.
- [**view**](#agrag-common-data_models-task-TaskLookup-view) (<code>[TaskView](TaskView.md) | None</code>) – The resume view, or None when the task is not found.

## `found` \{#agrag-common-data_models-task-TaskLookup-found}

```python
found: bool
```

## `model_config` \{#agrag-common-data_models-task-TaskLookup-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `view` \{#agrag-common-data_models-task-TaskLookup-view}

```python
view: TaskView | None = None
```
