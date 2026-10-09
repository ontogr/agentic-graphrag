---
title: agrag.eval.trajectory.retry_budget_metric
sidebar_label: retry_budget_metric
---

# `agrag.eval.trajectory.retry_budget_metric` \{#agrag-eval-trajectory-retry_budget_metric}

```python
retry_budget_metric(max_attempts:int, *, threshold:float = 0.5) -> ScoreMetric
```

Build the metric that retries stay within budget.

Counts researcher `task` spans starting after the first verifier
`task` span ended. A call the limiter blocks leaves no span, so only
executed delegations count. Scores 1.0 or 0.0.

**Parameters:**

- **max_attempts** (<code>int</code>) – How many researcher retries after verification pass.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>[ScoreMetric](../adapter/ScoreMetric.md)</code> – A `ScoreMetric` that scores the retry budget.
