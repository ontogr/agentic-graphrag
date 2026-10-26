---
title: agrag.eval.answer.context_recall
sidebar_label: context_recall
---

# `agrag.eval.answer.context_recall` \{#agrag-eval-answer-context_recall}

```python
context_recall(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> BaseMetric
```

Build the metric for reference facts that the evidence covers.

**Parameters:**

- **judge** (<code>DeepEvalBaseLLM</code>) – The judge model.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>BaseMetric</code> – The context recall metric.
