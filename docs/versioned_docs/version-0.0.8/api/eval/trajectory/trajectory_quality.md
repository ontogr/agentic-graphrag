---
title: agrag.eval.trajectory.trajectory_quality
sidebar_label: trajectory_quality
---

# `agrag.eval.trajectory.trajectory_quality` \{#agrag-eval-trajectory-trajectory_quality}

```python
trajectory_quality(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> BaseMetric
```

Build the judged metric for trajectory quality.

Scores whether the steps follow logically from the question, with no
reference trajectory and one judge call. The gate is the mean over
questions, following the answer-quality eval.

**Parameters:**

- **judge** (<code>DeepEvalBaseLLM</code>) – The judge model. Its chat model grades the trajectory.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>BaseMetric</code> – The trajectory quality metric.

**Raises:**

- <code>TypeError</code> – The judge holds no LangChain chat model.
