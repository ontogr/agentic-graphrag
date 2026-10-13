---
title: agrag.agents.tracing.run_callbacks
sidebar_label: run_callbacks
---

# `agrag.agents.tracing.run_callbacks` \{#agrag-agents-tracing-run_callbacks}

```python
run_callbacks(tracer:Tracer | None) -> list[Any]
```

Return the callbacks for one agent run.

The callback holds per-run state, so build a new one for every run.
Spans carry the question, tool inputs, and evidence text.

**Parameters:**

- **tracer** (<code>Tracer | None</code>) – The tracer that receives the spans, or `None` to disable
  tracing.

**Returns:**

- <code>list\[Any\]</code> – A one-item callback list, or an empty list when `tracer` is `None`.
