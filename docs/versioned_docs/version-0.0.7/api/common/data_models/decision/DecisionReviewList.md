---
title: agrag.common.data_models.decision.DecisionReviewList
sidebar_label: DecisionReviewList
---

# `agrag.common.data_models.decision.DecisionReviewList` \{#agrag-common-data_models-decision-DecisionReviewList}

Bases: <code>BaseModel</code>

A bounded project-scoped page of decisions requiring review.

**Attributes:**

- [**count**](#agrag-common-data_models-decision-DecisionReviewList-count) (<code>int</code>) –
- [**decisions**](#agrag-common-data_models-decision-DecisionReviewList-decisions) (<code>list\[[Decision](Decision-ref.md)\]</code>) –
- [**model_config**](#agrag-common-data_models-decision-DecisionReviewList-model_config) –
- [**truncated**](#agrag-common-data_models-decision-DecisionReviewList-truncated) (<code>bool</code>) –

## `count` \{#agrag-common-data_models-decision-DecisionReviewList-count}

```python
count: int = 0
```

## `decisions` \{#agrag-common-data_models-decision-DecisionReviewList-decisions}

```python
decisions: list[Decision] = Field(default_factory=list)
```

## `model_config` \{#agrag-common-data_models-decision-DecisionReviewList-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `truncated` \{#agrag-common-data_models-decision-DecisionReviewList-truncated}

```python
truncated: bool = False
```
