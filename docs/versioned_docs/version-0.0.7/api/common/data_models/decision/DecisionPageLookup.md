---
title: agrag.common.data_models.decision.DecisionPageLookup
sidebar_label: DecisionPageLookup
---

# `agrag.common.data_models.decision.DecisionPageLookup` \{#agrag-common-data_models-decision-DecisionPageLookup}

Bases: <code>BaseModel</code>

The result of listing a task's decisions by name.

**Attributes:**

- [**found**](#agrag-common-data_models-decision-DecisionPageLookup-found) (<code>bool</code>) – Whether a task with that name exists in the project.
- [**page**](#agrag-common-data_models-decision-DecisionPageLookup-page) (<code>[DecisionPage](DecisionPage.md)</code>) – The decisions of the task, or an empty page when not found.

## `found` \{#agrag-common-data_models-decision-DecisionPageLookup-found}

```python
found: bool
```

## `model_config` \{#agrag-common-data_models-decision-DecisionPageLookup-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `page` \{#agrag-common-data_models-decision-DecisionPageLookup-page}

```python
page: DecisionPage = Field(default_factory=DecisionPage)
```
