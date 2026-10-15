---
title: agrag.common.data_models.task.Event
sidebar_label: Event
---

# `agrag.common.data_models.task.Event` \{#agrag-common-data_models-task-Event}

Bases: <code>BaseModel</code>

One raw event appended to a task.

**Attributes:**

- [**id**](#agrag-common-data_models-task-Event-id) (<code>UUID</code>) – Identifier derived from the task id and the sequence number.
- [**task_id**](#agrag-common-data_models-task-Event-task_id) (<code>UUID</code>) – The task the event belongs to.
- [**seq**](#agrag-common-data_models-task-Event-seq) (<code>int</code>) – Gapless position of the event in its task, starting at 1.
- [**kind**](#agrag-common-data_models-task-Event-kind) (<code>[EventKind](EventKind.md)</code>) – Kind of event.
- [**role**](#agrag-common-data_models-task-Event-role) (<code>str | None</code>) – Speaker role for a message, or None.
- [**name**](#agrag-common-data_models-task-Event-name) (<code>str | None</code>) – Tool or source name for a tool event, or None.
- [**payload**](#agrag-common-data_models-task-Event-payload) (<code>str</code>) – Stored event text. Cut to the payload limit when
  `truncated` is true.
- [**payload_sha256**](#agrag-common-data_models-task-Event-payload_sha256) (<code>str</code>) – SHA-256 of the full text, before any cut.
- [**truncated**](#agrag-common-data_models-task-Event-truncated) (<code>bool</code>) – Whether the stored payload is shorter than the full text.
- [**author**](#agrag-common-data_models-task-Event-author) (<code>str</code>) – The agent that recorded the event.
- [**at**](#agrag-common-data_models-task-Event-at) (<code>datetime</code>) – When the event was recorded.

## `at` \{#agrag-common-data_models-task-Event-at}

```python
at: datetime
```

## `author` \{#agrag-common-data_models-task-Event-author}

```python
author: str
```

## `id` \{#agrag-common-data_models-task-Event-id}

```python
id: UUID
```

## `kind` \{#agrag-common-data_models-task-Event-kind}

```python
kind: EventKind
```

## `model_config` \{#agrag-common-data_models-task-Event-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `name` \{#agrag-common-data_models-task-Event-name}

```python
name: str | None
```

## `payload` \{#agrag-common-data_models-task-Event-payload}

```python
payload: str
```

## `payload_sha256` \{#agrag-common-data_models-task-Event-payload_sha256}

```python
payload_sha256: str
```

## `role` \{#agrag-common-data_models-task-Event-role}

```python
role: str | None
```

## `seq` \{#agrag-common-data_models-task-Event-seq}

```python
seq: int
```

## `task_id` \{#agrag-common-data_models-task-Event-task_id}

```python
task_id: UUID
```

## `truncated` \{#agrag-common-data_models-task-Event-truncated}

```python
truncated: bool
```
