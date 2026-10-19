---
title: agrag.common.data_models.decision.DecisionSupport
sidebar_label: DecisionSupport
---

# `agrag.common.data_models.decision.DecisionSupport` \{#agrag-common-data_models-decision-DecisionSupport}

Bases: <code>BaseModel</code>

A stored dependency on another decision.

**Attributes:**

- [**kind**](#agrag-common-data_models-decision-DecisionSupport-kind) (<code>Literal\[[DECISION](SupportKind.md#agrag-common-data_models-decision-SupportKind-DECISION)\]</code>) – Always `decision`.
- [**decision_id**](#agrag-common-data_models-decision-DecisionSupport-decision_id) (<code>UUID</code>) – The id of the decision depended on.

## `current` \{#agrag-common-data_models-decision-DecisionSupport-current}

```python
current: bool = True
```

## `decision_id` \{#agrag-common-data_models-decision-DecisionSupport-decision_id}

```python
decision_id: UUID
```

## `kind` \{#agrag-common-data_models-decision-DecisionSupport-kind}

```python
kind: Literal[SupportKind.DECISION]
```

## `model_config` \{#agrag-common-data_models-decision-DecisionSupport-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `review_explanation` \{#agrag-common-data_models-decision-DecisionSupport-review_explanation}

```python
review_explanation: str | None = None
```

## `reviewed_at` \{#agrag-common-data_models-decision-DecisionSupport-reviewed_at}

```python
reviewed_at: datetime | None = None
```

## `reviewed_by` \{#agrag-common-data_models-decision-DecisionSupport-reviewed_by}

```python
reviewed_by: str | None = None
```
