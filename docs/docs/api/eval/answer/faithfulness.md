---
title: agrag.eval.answer.faithfulness
sidebar_label: faithfulness
---

# `agrag.eval.answer.faithfulness` \{#agrag-eval-answer-faithfulness}

```python
faithfulness(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> BaseMetric
```

Build the metric for claims that the evidence the agent saw does not contradict.

A claim that the evidence does not mention counts as faithful. Only a claim
that the evidence contradicts lowers the score. `CitationAccuracyMetric`
catches unsupported claims.

**Parameters:**

- **judge** (<code>DeepEvalBaseLLM</code>) – The judge model.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>BaseMetric</code> – The faithfulness metric.
