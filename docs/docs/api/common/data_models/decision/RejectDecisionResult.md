---
title: agrag.common.data_models.decision.RejectDecisionResult
sidebar_label: RejectDecisionResult
---

# `agrag.common.data_models.decision.RejectDecisionResult` \{#agrag-common-data_models-decision-RejectDecisionResult}

Bases: <code>[WriteResult](../memory_result/WriteResult.md)</code>

The outcome of rejecting a decision.

**Attributes:**

- [**decision**](#agrag-common-data_models-decision-RejectDecisionResult-decision) (<code>[Decision](Decision-ref.md) | None</code>) – The rejected decision when `recorded` is true.

## `decision` \{#agrag-common-data_models-decision-RejectDecisionResult-decision}

```python
decision: Decision | None = None
```

## `error` \{#agrag-common-data_models-decision-RejectDecisionResult-error}

```python
error: MemoryErrorCode | None = None
```

## `model_config` \{#agrag-common-data_models-decision-RejectDecisionResult-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `recorded` \{#agrag-common-data_models-decision-RejectDecisionResult-recorded}

```python
recorded: bool
```
