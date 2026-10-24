---
title: agrag.eval.trajectory.expected_tools_metric
sidebar_label: expected_tools_metric
---

# `agrag.eval.trajectory.expected_tools_metric` \{#agrag-eval-trajectory-expected_tools_metric}

```python
expected_tools_metric(names:Sequence[str | Sequence[str]], *, threshold:float = 0.5) -> ScoreMetric
```

Build the metric that the run made every expected tool call.

Compares the trajectory's tool call names with the expected entries,
ignoring arguments: extra calls do not matter, and every entry must be
satisfied. A name is satisfied when it was called; a nested sequence is
satisfied when any one of its names was called. Scores 1.0 or 0.0.

**Parameters:**

- **names** (<code>Sequence\[str | Sequence\[str\]\]</code>) – The tool calls the run must include. Each item is one
  required name, or a set of alternative names of which the run
  must have called at least one.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>[ScoreMetric](../adapter/ScoreMetric.md)</code> – A `ScoreMetric` that scores tool presence.
