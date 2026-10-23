---
title: agrag.common.data_models.decision.ReaffirmDecisionResult
sidebar_label: ReaffirmDecisionResult
---

# `agrag.common.data_models.decision.ReaffirmDecisionResult` \{#agrag-common-data_models-decision-ReaffirmDecisionResult}

Bases: <code>[WriteResult](../write_result/WriteResult.md)</code>

The outcome of reaffirming a flagged decision.

**Attributes:**

- [**decision**](#agrag-common-data_models-decision-ReaffirmDecisionResult-decision) (<code>[Decision](Decision-ref.md) | None</code>) – The reaffirmed decision when `recorded` is true.

## `decision` \{#agrag-common-data_models-decision-ReaffirmDecisionResult-decision}

```python
decision: Decision | None = None
```

## `error` \{#agrag-common-data_models-decision-ReaffirmDecisionResult-error}

```python
error: WriteErrorCode | None = None
```

## `model_config` \{#agrag-common-data_models-decision-ReaffirmDecisionResult-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `recorded` \{#agrag-common-data_models-decision-ReaffirmDecisionResult-recorded}

```python
recorded: bool
```
