---
title: agrag.eval.trajectory.verifier_before_answer_metric
sidebar_label: verifier_before_answer_metric
---

# `agrag.eval.trajectory.verifier_before_answer_metric` \{#agrag-eval-trajectory-verifier_before_answer_metric}

```python
verifier_before_answer_metric(*, threshold:float = 0.5) -> ScoreMetric
```

Build the metric that the verifier ran before the answer.

Passes when the planner's last `LLM` span starts after at least one
verifier `task` span ended. Scores 1.0 or 0.0.

**Parameters:**

- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>[ScoreMetric](../adapter/ScoreMetric.md)</code> – A `ScoreMetric` that scores verifier-before-answer.
