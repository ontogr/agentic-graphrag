---
title: agrag.eval.verifier.verdict_match_metric
sidebar_label: verdict_match_metric
---

# `agrag.eval.verifier.verdict_match_metric` \{#agrag-eval-verifier-verdict_match_metric}

```python
verdict_match_metric(*, threshold:float = 0.0) -> ScoreMetric
```

Build a metric that scores 1.0 when the verdict equals the gold verdict.

The default threshold is 0 because the gate belongs on the macro F1 of
`verdict_report`.

**Parameters:**

- **threshold** (<code>float</code>) – The minimum case score that counts as success.

**Returns:**

- <code>[ScoreMetric](../adapter/ScoreMetric.md)</code> – A `ScoreMetric` that scores verdict equality against `threshold`.
