---
title: agrag.common.data_models.task.StepPage
sidebar_label: StepPage
---

# `agrag.common.data_models.task.StepPage` \{#agrag-common-data_models-task-StepPage}

Bases: <code>BaseModel</code>

One bounded page of steps in a task and state.

**Attributes:**

- [**model_config**](#agrag-common-data_models-task-StepPage-model_config) –
- [**next_after_name**](#agrag-common-data_models-task-StepPage-next_after_name) (<code>str | None</code>) –
- [**steps**](#agrag-common-data_models-task-StepPage-steps) (<code>list\[[StepSummary](StepSummary.md)\]</code>) –
- [**truncated**](#agrag-common-data_models-task-StepPage-truncated) (<code>bool</code>) –

## `model_config` \{#agrag-common-data_models-task-StepPage-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `next_after_name` \{#agrag-common-data_models-task-StepPage-next_after_name}

```python
next_after_name: str | None = None
```

## `steps` \{#agrag-common-data_models-task-StepPage-steps}

```python
steps: list[StepSummary] = Field(default_factory=list)
```

## `truncated` \{#agrag-common-data_models-task-StepPage-truncated}

```python
truncated: bool = False
```
