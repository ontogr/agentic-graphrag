---
title: agrag.eval.cluster_quality_metric
sidebar_label: cluster_quality_metric
---

# `agrag.eval.cluster_quality_metric` \{#agrag-eval-cluster_quality_metric}

```python
cluster_quality_metric(*, threshold:float = 0.5) -> ScoreMetric
```

Build a metric for cluster quality on one test case.

The score is B-cubed F1. The breakdown holds `b_cubed_precision`,
`b_cubed_recall`, `pairwise_precision`, `pairwise_recall` and
`pairwise_f`. An over-merge lowers precision and an under-merge lowers
recall. The score of a whole dataset is the score of one case that holds
all its mentions, because pooling clusters from separate cases is not
defined.

**Parameters:**

- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>[ScoreMetric](adapter/ScoreMetric.md)</code> – A metric that scores one case from `resolution_case`.
