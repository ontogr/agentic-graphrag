---
title: agrag.common.data_models.retention.RetentionResult
sidebar_label: RetentionResult
---

# `agrag.common.data_models.retention.RetentionResult` \{#agrag-common-data_models-retention-RetentionResult}

Bases: <code>BaseModel</code>

Outcome of a retention operation.

**Attributes:**

- [**affected_decision_ids**](#agrag-common-data_models-retention-RetentionResult-affected_decision_ids) (<code>list\[str\]</code>) –
- [**error**](#agrag-common-data_models-retention-RetentionResult-error) (<code>[RetentionErrorCode](RetentionErrorCode.md) | None</code>) –
- [**model_config**](#agrag-common-data_models-retention-RetentionResult-model_config) –
- [**recorded**](#agrag-common-data_models-retention-RetentionResult-recorded) (<code>bool</code>) –

## `affected_decision_ids` \{#agrag-common-data_models-retention-RetentionResult-affected_decision_ids}

```python
affected_decision_ids: list[str] = Field(default_factory=list)
```

## `error` \{#agrag-common-data_models-retention-RetentionResult-error}

```python
error: RetentionErrorCode | None = None
```

## `model_config` \{#agrag-common-data_models-retention-RetentionResult-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `recorded` \{#agrag-common-data_models-retention-RetentionResult-recorded}

```python
recorded: bool
```
