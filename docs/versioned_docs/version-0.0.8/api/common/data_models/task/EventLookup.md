---
title: agrag.common.data_models.task.EventLookup
sidebar_label: EventLookup
---

# `agrag.common.data_models.task.EventLookup` \{#agrag-common-data_models-task-EventLookup}

Bases: <code>BaseModel</code>

The result of reading one event by task and sequence number.

**Attributes:**

- [**event**](#agrag-common-data_models-task-EventLookup-event) (<code>[Event](Event.md) | None</code>) –
- [**found**](#agrag-common-data_models-task-EventLookup-found) (<code>bool</code>) –
- [**model_config**](#agrag-common-data_models-task-EventLookup-model_config) –

## `event` \{#agrag-common-data_models-task-EventLookup-event}

```python
event: Event | None = None
```

## `found` \{#agrag-common-data_models-task-EventLookup-found}

```python
found: bool
```

## `model_config` \{#agrag-common-data_models-task-EventLookup-model_config}

```python
model_config = ConfigDict(frozen=True)
```
