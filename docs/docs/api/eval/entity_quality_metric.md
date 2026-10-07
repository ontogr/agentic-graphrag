---
title: agrag.eval.entity_quality_metric
sidebar_label: entity_quality_metric
---

# `agrag.eval.entity_quality_metric` \{#agrag-eval-entity_quality_metric}

```python
entity_quality_metric(*, threshold:float = 0.0) -> ScoreMetric
```

Build a metric for entity F1 on one test case.

The case score is the exact F1. Use a new metric for each case, and pass the
measured metrics to `micro_scores`. The default threshold is 0 because the
gate belongs on the dataset score.

**Parameters:**

- **threshold** (<code>float</code>) – The minimum case score that counts as success.

**Returns:**

- <code>[ScoreMetric](adapter/ScoreMetric.md)</code> – A metric that scores exact entity F1 for one case.
