---
title: agrag.eval.trajectory.expected_tools_metric
sidebar_label: expected_tools_metric
---

# `agrag.eval.trajectory.expected_tools_metric` \{#agrag-eval-trajectory-expected_tools_metric}

```python
expected_tools_metric(names:Sequence[str], *, threshold:float = 0.5) -> ScoreMetric
```

Build the metric that the run called every expected tool.

Compares the trajectory's tool calls with the expected names as a
superset, ignoring arguments: extra tools do not matter, a missing name
fails. Scores 1.0 or 0.0.

**Parameters:**

- **names** (<code>Sequence\[str\]</code>) – The tool names the run must include.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>[ScoreMetric](../adapter/ScoreMetric.md)</code> – A `ScoreMetric` that scores tool presence.
