---
title: agrag.eval.trajectory.expected_tools_metric
sidebar_label: expected_tools_metric
---

# `agrag.eval.trajectory.expected_tools_metric` \{#agrag-eval-trajectory-expected_tools_metric}

```python
expected_tools_metric(names:Sequence[str | Sequence[str]], *, threshold:float = 0.5) -> ScoreMetric
```

Build the metric that the run made every expected tool call, in order.

Matches the expected entries against the trajectory's tool call names,
ignoring arguments: every entry must be satisfied, in order, as a
subsequence of the calls, and extra calls do not matter. A name is
satisfied by a call to that name; a nested sequence by a call to any
one of its names. A repeated entry needs a separate call per
occurrence, so discovery before fetch and repeated searches are both
enforced. Scores 1.0 or 0.0.

**Parameters:**

- **names** (<code>Sequence\[str | Sequence\[str\]\]</code>) – The tool calls the run must make, in order. Each item is one
  required name, or a non-empty set of alternative names of which
  the run must have called at least one.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>[ScoreMetric](../adapter/ScoreMetric.md)</code> – A `ScoreMetric` that scores tool presence and order.

**Raises:**

- <code>ValueError</code> – An alternative group holds no names.
