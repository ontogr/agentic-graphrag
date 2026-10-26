---
title: agrag.eval.resolution.resolution_case
sidebar_label: resolution_case
---

# `agrag.eval.resolution.resolution_case` \{#agrag-eval-resolution-resolution_case}

```python
resolution_case(mentions:Sequence[str], predicted:ClusterAssignment, gold:ClusterAssignment) -> LLMTestCase
```

Build a test case that holds predicted and gold clusters.

**Parameters:**

- **mentions** (<code>Sequence\[str\]</code>) – The mention texts. They show in DeepEval reports.
- **predicted** (<code>[ClusterAssignment](ClusterAssignment.md)</code>) – The clusters the resolver formed.
- **gold** (<code>[ClusterAssignment](ClusterAssignment.md)</code>) – The gold clusters.

**Returns:**

- <code>LLMTestCase</code> – A test case with serialized predicted and gold clusters.
