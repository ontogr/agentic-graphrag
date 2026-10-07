---
title: agrag.eval.answer.context_precision
sidebar_label: context_precision
---

# `agrag.eval.answer.context_precision` \{#agrag-eval-answer-context_precision}

```python
context_precision(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> BaseMetric
```

Build the metric for useful evidence ranked before noise.

**Parameters:**

- **judge** (<code>DeepEvalBaseLLM</code>) – The judge model.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>BaseMetric</code> – The context precision metric.
