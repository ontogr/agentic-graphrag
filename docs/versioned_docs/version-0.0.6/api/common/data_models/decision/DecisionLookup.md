---
title: agrag.common.data_models.decision.DecisionLookup
sidebar_label: DecisionLookup
---

# `agrag.common.data_models.decision.DecisionLookup` \{#agrag-common-data_models-decision-DecisionLookup}

Bases: <code>BaseModel</code>

The result of reading one decision by id.

**Attributes:**

- [**found**](#agrag-common-data_models-decision-DecisionLookup-found) (<code>bool</code>) – Whether a decision with that id exists in the project.
- [**decision**](#agrag-common-data_models-decision-DecisionLookup-decision) (<code>[Decision](Decision-ref.md) | None</code>) – The decision with its supports, or None when not found.

## `decision` \{#agrag-common-data_models-decision-DecisionLookup-decision}

```python
decision: Decision | None = None
```

## `found` \{#agrag-common-data_models-decision-DecisionLookup-found}

```python
found: bool
```

## `model_config` \{#agrag-common-data_models-decision-DecisionLookup-model_config}

```python
model_config = ConfigDict(frozen=True)
```
