---
title: agrag.common.data_models.decision.SupportHistoryPage
sidebar_label: SupportHistoryPage
---

# `agrag.common.data_models.decision.SupportHistoryPage` \{#agrag-common-data_models-decision-SupportHistoryPage}

Bases: <code>BaseModel</code>

A bounded page of immutable support references and review transitions.

**Attributes:**

- [**model_config**](#agrag-common-data_models-decision-SupportHistoryPage-model_config) –
- [**next_after_ordinal**](#agrag-common-data_models-decision-SupportHistoryPage-next_after_ordinal) (<code>int | None</code>) –
- [**supports**](#agrag-common-data_models-decision-SupportHistoryPage-supports) (<code>list\[[Support](Support.md)\]</code>) –
- [**truncated**](#agrag-common-data_models-decision-SupportHistoryPage-truncated) (<code>bool</code>) –

## `model_config` \{#agrag-common-data_models-decision-SupportHistoryPage-model_config}

```python
model_config = ConfigDict(frozen=True)
```

## `next_after_ordinal` \{#agrag-common-data_models-decision-SupportHistoryPage-next_after_ordinal}

```python
next_after_ordinal: int | None = None
```

## `supports` \{#agrag-common-data_models-decision-SupportHistoryPage-supports}

```python
supports: list[Support] = Field(default_factory=list)
```

## `truncated` \{#agrag-common-data_models-decision-SupportHistoryPage-truncated}

```python
truncated: bool = False
```
