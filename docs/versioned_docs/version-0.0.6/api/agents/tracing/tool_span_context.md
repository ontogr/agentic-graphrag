---
title: agrag.agents.tracing.tool_span_context
sidebar_label: tool_span_context
---

# `agrag.agents.tracing.tool_span_context` \{#agrag-agents-tracing-tool_span_context}

```python
tool_span_context(callbacks:Any) -> AbstractContextManager[Any]
```

Return a context in which the running tool's OpenInference span is current.

The OpenInference callback never makes its spans current, so a span that
`agrag` opens inside a tool would otherwise be a sibling of the tool's
span, not its child. A tool declares `callbacks: Any = None`; LangChain
then passes a child callback manager whose `parent_run_id` is the tool's
run and whose handlers include the callback. The context makes the tool's
span current for the tool's body and restores the caller's context on
exit. It leaves the tool span's status and events to the callback, so a
raising tool records its exception once.

**Parameters:**

- **callbacks** (<code>Any</code>) – The `callbacks` argument LangChain injected, or `None`
  when the caller passed none.

**Returns:**

- <code>AbstractContextManager\[Any\]</code> – A context making the tool's `TOOL` span current, or a no-op context
- <code>AbstractContextManager\[Any\]</code> – when there is no OpenInference handler, which is the case whenever
- <code>AbstractContextManager\[Any\]</code> – `build_agent` was given no tracer.
