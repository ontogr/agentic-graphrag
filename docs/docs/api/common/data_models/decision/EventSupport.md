---
title: agrag.common.data_models.decision.EventSupport
sidebar_label: EventSupport
---

# `agrag.common.data_models.decision.EventSupport` \{#agrag-common-data_models-decision-EventSupport}

Bases: <code>BaseModel</code>

A stored event support.

**Attributes:**

- [**kind**](#agrag-common-data_models-decision-EventSupport-kind) (<code>Literal\[[EVENT](SupportKind.md#agrag-common-data_models-decision-SupportKind-EVENT)\]</code>) – Always `event`.
- [**event_id**](#agrag-common-data_models-decision-EventSupport-event_id) (<code>UUID</code>) – The id of the event node.
- [**task_name**](#agrag-common-data_models-decision-EventSupport-task_name) (<code>str</code>) – The task that holds the event.
- [**seq**](#agrag-common-data_models-decision-EventSupport-seq) (<code>int</code>) – The sequence number of the event in that task.

## `event_id` \{#agrag-common-data_models-decision-EventSupport-event_id}

```python
event_id: UUID
```

## `kind` \{#agrag-common-data_models-decision-EventSupport-kind}

```python
kind: Literal[SupportKind.EVENT]
```

## `model_config` \{#agrag-common-data_models-decision-EventSupport-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `seq` \{#agrag-common-data_models-decision-EventSupport-seq}

```python
seq: int
```

## `task_name` \{#agrag-common-data_models-decision-EventSupport-task_name}

```python
task_name: str
```
