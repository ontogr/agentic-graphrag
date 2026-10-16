---
title: agrag.common.data_models.decision.EventSupportInput
sidebar_label: EventSupportInput
---

# `agrag.common.data_models.decision.EventSupportInput` \{#agrag-common-data_models-decision-EventSupportInput}

Bases: <code>BaseModel</code>

An existing event of a task in the same project.

**Attributes:**

- [**task_name**](#agrag-common-data_models-decision-EventSupportInput-task_name) (<code>str</code>) – The task that holds the event.
- [**seq**](#agrag-common-data_models-decision-EventSupportInput-seq) (<code>int</code>) – The sequence number of the event in that task.

## `model_config` \{#agrag-common-data_models-decision-EventSupportInput-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `seq` \{#agrag-common-data_models-decision-EventSupportInput-seq}

```python
seq: int
```

## `task_name` \{#agrag-common-data_models-decision-EventSupportInput-task_name}

```python
task_name: str
```
