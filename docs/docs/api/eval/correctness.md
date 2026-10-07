---
title: agrag.eval.correctness
sidebar_label: correctness
---

# `agrag.eval.correctness` \{#agrag-eval-correctness}

```python
correctness(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> BaseMetric
```

Build the answer correctness metric against the reference.

**Parameters:**

- **judge** (<code>DeepEvalBaseLLM</code>) – The judge model.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>BaseMetric</code> – The correctness metric.
