---
title: agrag.agents.middleware.VerifierEvidenceMiddleware
sidebar_label: VerifierEvidenceMiddleware
---

# `agrag.agents.middleware.VerifierEvidenceMiddleware` \{#agrag-agents-middleware-VerifierEvidenceMiddleware}

```python
VerifierEvidenceMiddleware(ledger:Ledger) -> None
```

Bases: <code>AgentMiddleware</code>

Give the verifier the evidence text behind each key a task cites.

The planner writes the verifier's task from the researcher's summary, so the
task carries citation keys and no evidence. The verifier has no tools, so it
cannot check that a key supports a claim. This middleware appends the ledger
text of every key in a verifier task, and marks a key that this run never
retrieved. Tasks for other subagents pass through unchanged.

Holds a run's `Ledger`, so construct one per `ainvoke` call.

**Functions:**

- [**awrap_tool_call**](#agrag-agents-middleware-VerifierEvidenceMiddleware-awrap_tool_call) – Append an Evidence block to a verifier task, then run the call.

**Parameters:**

- **ledger** (<code>[Ledger](../ledger/Ledger-ref.md)</code>) – The ledger of the run whose keys the planner cites.

## `awrap_tool_call` \{#agrag-agents-middleware-VerifierEvidenceMiddleware-awrap_tool_call}

```python
awrap_tool_call(request:ToolCallRequest, handler:Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]]) -> ToolMessage | Command[Any]
```

Append an Evidence block to a verifier task, then run the call.

**Parameters:**

- **request** (<code>ToolCallRequest</code>) – The intercepted tool call request.
- **handler** (<code>Callable\\[[ToolCallRequest\], Awaitable\[ToolMessage | Command\[Any\]\]\]</code>) – The rest of the tool-call pipeline.

**Returns:**

- <code>ToolMessage | Command\[Any\]</code> – The handler's result.
