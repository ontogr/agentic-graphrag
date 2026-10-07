---
title: agrag.eval.trajectory_case
sidebar_label: trajectory_case
---

# `agrag.eval.trajectory_case` \{#agrag-eval-trajectory_case}

```python
trajectory_case(question:str, answer:str, trajectory:Trajectory) -> LLMTestCase
```

Build the test case every trajectory metric scores.

`tools_called` holds every `TOOL` step, planner and researcher, as a
`ToolCall`. `metadata["trajectory"]` holds the serialized trajectory
the deterministic metrics read.

**Parameters:**

- **question** (<code>str</code>) – The question the agent answered.
- **answer** (<code>str</code>) – The agent's final answer.
- **trajectory** (<code>[Trajectory](trajectory/Trajectory-ref.md)</code>) – The run's trajectory from `read_trajectory`.

**Returns:**

- <code>LLMTestCase</code> – The test case with the answer, the tool calls and the trajectory.
