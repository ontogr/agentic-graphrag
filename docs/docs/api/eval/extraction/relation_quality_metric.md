---
title: agrag.eval.extraction.relation_quality_metric
sidebar_label: relation_quality_metric
---

# `agrag.eval.extraction.relation_quality_metric` \{#agrag-eval-extraction-relation_quality_metric}

```python
relation_quality_metric(*, symmetric_labels:frozenset[str] = frozenset(), threshold:float = 0.0) -> ScoreMetric
```

Build a metric for relation triple F1 on one test case.

A relation counts only when both endpoints align to gold entities and the
triple is in gold. Use a new metric for each case.

**Parameters:**

- **symmetric_labels** (<code>frozenset\[str\]</code>) – Relation labels with no direction. Their two endpoints
  are sorted before comparison.
- **threshold** (<code>float</code>) – The minimum case score that counts as success.

**Returns:**

- <code>[ScoreMetric](../adapter/ScoreMetric.md)</code> – A metric that scores exact relation F1 for one case.
