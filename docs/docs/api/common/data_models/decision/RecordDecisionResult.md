---
title: agrag.common.data_models.decision.RecordDecisionResult
sidebar_label: RecordDecisionResult
---

# `agrag.common.data_models.decision.RecordDecisionResult` \{#agrag-common-data_models-decision-RecordDecisionResult}

Bases: <code>[WriteResult](../memory_result/WriteResult.md)</code>

The outcome of recording a decision.

**Attributes:**

- [**decision**](#agrag-common-data_models-decision-RecordDecisionResult-decision) (<code>[Decision](Decision-ref.md) | None</code>) – The stored decision when `recorded` is true.
- [**warnings**](#agrag-common-data_models-decision-RecordDecisionResult-warnings) (<code>list\[str\]</code>) – Notes for the caller, such as a source that changed while
  the decision was recorded.

## `decision` \{#agrag-common-data_models-decision-RecordDecisionResult-decision}

```python
decision: Decision | None = None
```

## `error` \{#agrag-common-data_models-decision-RecordDecisionResult-error}

```python
error: MemoryErrorCode | None = None
```

## `model_config` \{#agrag-common-data_models-decision-RecordDecisionResult-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `recorded` \{#agrag-common-data_models-decision-RecordDecisionResult-recorded}

```python
recorded: bool
```

## `warnings` \{#agrag-common-data_models-decision-RecordDecisionResult-warnings}

```python
warnings: list[str] = Field(default_factory=list)
```
