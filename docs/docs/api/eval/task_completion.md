---
title: agrag.eval.task_completion
sidebar_label: task_completion
---

# `agrag.eval.task_completion` \{#agrag-eval-task_completion}

```python
task_completion(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> BaseMetric
```

Build the judged metric for task completion.

Scores whether the run achieved the question's goal, from the question,
the answer and the tool calls, with one judge call. The gate is the mean
over questions, following the answer-quality eval, so no median of
repeated calls is needed.

**Parameters:**

- **judge** (<code>DeepEvalBaseLLM</code>) – The judge model.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>BaseMetric</code> – The task completion metric.
