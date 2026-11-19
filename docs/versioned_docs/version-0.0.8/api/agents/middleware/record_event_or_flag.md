---
title: agrag.agents.middleware.record_event_or_flag
sidebar_label: record_event_or_flag
---

# `agrag.agents.middleware.record_event_or_flag` \{#agrag-agents-middleware-record_event_or_flag}

```python
record_event_or_flag(history:Any, task_name:str, run_state:RunState, kind:EventKind, *, payload:str, role:str | None = None, name:str | None = None) -> Any
```

Append one event, retry it once, and flag the run if it still fails.

The retry reuses one request id, so a write that committed before the
error returns its stored result instead of a second event.

**Parameters:**

- **history** (<code>Any</code>) – The conversation history that holds the event.
- **task_name** (<code>str</code>) – The task the event belongs to.
- **run_state** (<code>[RunState](RunState.md)</code>) – The run whose failure flag is set on a lasting error.
- **kind** (<code>[EventKind](../../common/data_models/task/EventKind.md)</code>) – The kind of event.
- **payload** (<code>str</code>) – The event text.
- **role** (<code>str | None</code>) – The speaker role for a message, or None.
- **name** (<code>str | None</code>) – The tool or source name for a tool event, or None.

**Returns:**

- <code>Any</code> – The stored event, or None when the write did not complete.
