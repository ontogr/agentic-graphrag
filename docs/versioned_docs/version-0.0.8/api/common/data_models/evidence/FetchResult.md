---
title: agrag.common.data_models.evidence.FetchResult
sidebar_label: FetchResult
---

# `agrag.common.data_models.evidence.FetchResult` \{#agrag-common-data_models-evidence-FetchResult}

Bases: <code>BaseModel</code>

The outcomes of one fetch call.

**Attributes:**

- [**outcomes**](#agrag-common-data_models-evidence-FetchResult-outcomes) (<code>list\[[FetchOutcome](FetchOutcome.md)\]</code>) – One outcome for each fetched id, in the order given. A serving
  layer may drop trailing outcomes to stay within a size limit.
- [**truncated**](#agrag-common-data_models-evidence-FetchResult-truncated) (<code>bool</code>) – True when the serving layer dropped outcomes to stay within
  a size limit.

## `outcomes` \{#agrag-common-data_models-evidence-FetchResult-outcomes}

```python
outcomes: list[FetchOutcome] = Field(default_factory=list)
```

## `truncated` \{#agrag-common-data_models-evidence-FetchResult-truncated}

```python
truncated: bool = False
```
