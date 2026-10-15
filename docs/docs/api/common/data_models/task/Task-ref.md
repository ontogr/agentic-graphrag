---
title: agrag.common.data_models.task.Task
sidebar_label: Task
---

# `agrag.common.data_models.task.Task` \{#agrag-common-data_models-task-Task}

Bases: <code>BaseModel</code>

A named unit of work inside one project.

**Attributes:**

- [**id**](#agrag-common-data_models-task-Task-id) (<code>UUID</code>) – Identifier derived from the project id and the task name.
- [**project_id**](#agrag-common-data_models-task-Task-project_id) (<code>str</code>) – The project that owns the task.
- [**name**](#agrag-common-data_models-task-Task-name) (<code>str</code>) – Task name, unique within the project.
- [**goal**](#agrag-common-data_models-task-Task-goal) (<code>str</code>) – The goal given when the task was created.
- [**status**](#agrag-common-data_models-task-Task-status) (<code>[TaskStatus](TaskStatus.md)</code>) – Lifecycle state.
- [**event_seq**](#agrag-common-data_models-task-Task-event_seq) (<code>int</code>) – The sequence number of the last event appended, or 0.
- [**author**](#agrag-common-data_models-task-Task-author) (<code>str</code>) – The agent that created the task.
- [**created_at**](#agrag-common-data_models-task-Task-created_at) (<code>datetime</code>) – When the task was created.

## `author` \{#agrag-common-data_models-task-Task-author}

```python
author: str
```

## `created_at` \{#agrag-common-data_models-task-Task-created_at}

```python
created_at: datetime
```

## `event_seq` \{#agrag-common-data_models-task-Task-event_seq}

```python
event_seq: int
```

## `goal` \{#agrag-common-data_models-task-Task-goal}

```python
goal: str
```

## `id` \{#agrag-common-data_models-task-Task-id}

```python
id: UUID
```

## `model_config` \{#agrag-common-data_models-task-Task-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `name` \{#agrag-common-data_models-task-Task-name}

```python
name: str
```

## `project_id` \{#agrag-common-data_models-task-Task-project_id}

```python
project_id: str
```

## `status` \{#agrag-common-data_models-task-Task-status}

```python
status: TaskStatus
```
