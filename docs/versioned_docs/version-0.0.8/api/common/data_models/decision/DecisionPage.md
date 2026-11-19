---
title: agrag.common.data_models.decision.DecisionPage
sidebar_label: DecisionPage
---

# `agrag.common.data_models.decision.DecisionPage` \{#agrag-common-data_models-decision-DecisionPage}

Bases: <code>BaseModel</code>

A capped list of decisions with the total that matched.

**Attributes:**

- [**decisions**](#agrag-common-data_models-decision-DecisionPage-decisions) (<code>list\[[Decision](Decision-ref.md)\]</code>) – The first decisions in the page order, at most the cap.
- [**count**](#agrag-common-data_models-decision-DecisionPage-count) (<code>int</code>) – The number of decisions that matched, including hidden ones.
- [**truncated**](#agrag-common-data_models-decision-DecisionPage-truncated) (<code>bool</code>) – Whether some matching decisions are not in `decisions`.

## `count` \{#agrag-common-data_models-decision-DecisionPage-count}

```python
count: int = 0
```

## `decisions` \{#agrag-common-data_models-decision-DecisionPage-decisions}

```python
decisions: list[Decision] = Field(default_factory=list)
```

## `model_config` \{#agrag-common-data_models-decision-DecisionPage-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `truncated` \{#agrag-common-data_models-decision-DecisionPage-truncated}

```python
truncated: bool = False
```
