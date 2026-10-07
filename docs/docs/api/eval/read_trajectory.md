---
title: agrag.eval.read_trajectory
sidebar_label: read_trajectory
---

# `agrag.eval.read_trajectory` \{#agrag-eval-read_trajectory}

```python
read_trajectory(spans:Sequence[ReadableSpan]) -> Trajectory
```

Read the tool and model steps from finished spans.

Keeps `TOOL` and `LLM` spans, drops `CHAIN` spans, and orders steps
by start time rather than export order. Skips spans `agrag` opens
itself and spans nested under an `agrag.eval.judge` span, so judge
calls and BAML request spans never read as planner steps. A step's
`subagent` is the `subagent_type` of its nearest ancestor `task`
span, or None for a planner step.

**Parameters:**

- **spans** (<code>Sequence\[ReadableSpan\]</code>) – The finished spans of one traced agent run.

**Returns:**

- <code>[Trajectory](trajectory/Trajectory-ref.md)</code> – The run's trajectory in start order.
