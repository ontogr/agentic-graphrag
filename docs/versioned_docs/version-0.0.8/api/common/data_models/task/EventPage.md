---
title: agrag.common.data_models.task.EventPage
sidebar_label: EventPage
---

# `agrag.common.data_models.task.EventPage` \{#agrag-common-data_models-task-EventPage}

Bases: <code>BaseModel</code>

One page of events of a task, in sequence order.

**Attributes:**

- [**found**](#agrag-common-data_models-task-EventPage-found) (<code>bool</code>) – Whether the task exists in the project.
- [**events**](#agrag-common-data_models-task-EventPage-events) (<code>list\[[Event](Event.md)\]</code>) – The events after the requested sequence number.
- [**truncated**](#agrag-common-data_models-task-EventPage-truncated) (<code>bool</code>) – Whether more events follow this page.
- [**next_after_seq**](#agrag-common-data_models-task-EventPage-next_after_seq) (<code>int | None</code>) – The `after_seq` value that fetches the next page,
  or None when no events follow.

## `events` \{#agrag-common-data_models-task-EventPage-events}

```python
events: list[Event]
```

## `found` \{#agrag-common-data_models-task-EventPage-found}

```python
found: bool
```

## `model_config` \{#agrag-common-data_models-task-EventPage-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `next_after_seq` \{#agrag-common-data_models-task-EventPage-next_after_seq}

```python
next_after_seq: int | None = None
```

## `truncated` \{#agrag-common-data_models-task-EventPage-truncated}

```python
truncated: bool
```
