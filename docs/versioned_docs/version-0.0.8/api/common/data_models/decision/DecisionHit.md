---
title: agrag.common.data_models.decision.DecisionHit
sidebar_label: DecisionHit
---

# `agrag.common.data_models.decision.DecisionHit` \{#agrag-common-data_models-decision-DecisionHit}

Bases: <code>BaseModel</code>

A decision returned by precedent search.

The marker says the decision is a precedent to read. The model has no field
that says the decision applies to the current task.

**Attributes:**

- [**decision**](#agrag-common-data_models-decision-DecisionHit-decision) (<code>[Decision](Decision-ref.md)</code>) – The decision, with its task name, status and review state.
- [**task_goal**](#agrag-common-data_models-decision-DecisionHit-task_goal) (<code>str</code>) – The goal of the task that recorded the decision.
- [**marker**](#agrag-common-data_models-decision-DecisionHit-marker) (<code>Literal['precedent']</code>) – Always `precedent`.

## `decision` \{#agrag-common-data_models-decision-DecisionHit-decision}

```python
decision: Decision
```

## `marker` \{#agrag-common-data_models-decision-DecisionHit-marker}

```python
marker: Literal['precedent'] = PRECEDENT_MARKER
```

## `model_config` \{#agrag-common-data_models-decision-DecisionHit-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `task_goal` \{#agrag-common-data_models-decision-DecisionHit-task_goal}

```python
task_goal: str
```
