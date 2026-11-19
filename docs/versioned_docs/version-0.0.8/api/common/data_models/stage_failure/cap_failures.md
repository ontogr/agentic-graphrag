---
title: agrag.common.data_models.stage_failure.cap_failures
sidebar_label: cap_failures
---

# `agrag.common.data_models.stage_failure.cap_failures` \{#agrag-common-data_models-stage_failure-cap_failures}

```python
cap_failures(failures:list[StageFailure]) -> CappedFailures
```

Return failures capped per stage, with the untruncated true count.

Logs a warning when truncation occurs, since the capped list alone no
longer reflects how many items actually failed.

**Parameters:**

- **failures** (<code>list\[[StageFailure](StageFailure.md)\]</code>) – Every failure the stage recorded.

**Returns:**

- <code>[CappedFailures](CappedFailures.md)</code> – The capped list, the true failure count, and whether the list was
- <code>[CappedFailures](CappedFailures.md)</code> – truncated.
