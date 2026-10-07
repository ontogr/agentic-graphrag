---
title: agrag.common.data_models.stage_failure.CappedFailures
sidebar_label: CappedFailures
---

# `agrag.common.data_models.stage_failure.CappedFailures` \{#agrag-common-data_models-stage_failure-CappedFailures}

Bases: <code>NamedTuple</code>

A capped failure list plus the true count it was built from.

**Attributes:**

- [**items**](#agrag-common-data_models-stage_failure-CappedFailures-items) (<code>list\[[StageFailure](StageFailure.md)\]</code>) – The failure records, truncated to the per-stage cap.
- [**total**](#agrag-common-data_models-stage_failure-CappedFailures-total) (<code>int</code>) – How many failures the stage actually recorded, before any
  truncation.
- [**truncated**](#agrag-common-data_models-stage_failure-CappedFailures-truncated) (<code>bool</code>) – Whether `items` was cut to the per-stage cap.

## `items` \{#agrag-common-data_models-stage_failure-CappedFailures-items}

```python
items: list[StageFailure]
```

## `total` \{#agrag-common-data_models-stage_failure-CappedFailures-total}

```python
total: int
```

## `truncated` \{#agrag-common-data_models-stage_failure-CappedFailures-truncated}

```python
truncated: bool
```
