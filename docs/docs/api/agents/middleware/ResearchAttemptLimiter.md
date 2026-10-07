---
title: agrag.agents.middleware.ResearchAttemptLimiter
sidebar_label: ResearchAttemptLimiter
---

# `agrag.agents.middleware.ResearchAttemptLimiter` \{#agrag-agents-middleware-ResearchAttemptLimiter}

```python
ResearchAttemptLimiter(max_attempts:int) -> None
```

Bases: <code>AgentMiddleware</code>

Cap how many times the planner may re-delegate after verification.

Intercepts the generated `task` tool call and counts only
delegations to the researcher that follow at least one prior
delegation to the verifier. Once the cap is reached, short-circuits
with a message telling the planner to synthesize from evidence
already gathered, instead of letting the graph run until
`recursion_limit` aborts it with an opaque `GraphRecursionError`.

Holds per-run state, so construct one per `ainvoke` call, never
shared across runs.

**Functions:**

- [**awrap_tool_call**](#agrag-agents-middleware-ResearchAttemptLimiter-awrap_tool_call) – Count or short-circuit one task tool call.

**Parameters:**

- **max_attempts** (<code>int</code>) – How many researcher re-delegations after the
  first verifier consultation the planner may make.

**Raises:**

- <code>ValueError</code> – max_attempts is negative.

## `awrap_tool_call` \{#agrag-agents-middleware-ResearchAttemptLimiter-awrap_tool_call}

```python
awrap_tool_call(request:ToolCallRequest, handler:Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]]) -> ToolMessage | Command[Any]
```

Count or short-circuit one task tool call.

**Parameters:**

- **request** (<code>ToolCallRequest</code>) – The intercepted tool call request.
- **handler** (<code>Callable\\[[ToolCallRequest\], Awaitable\[ToolMessage | Command\[Any\]\]\]</code>) – The rest of the tool-call pipeline.

**Returns:**

- <code>ToolMessage | Command\[Any\]</code> – The handler's result, or the limit-reached ToolMessage when
- <code>ToolMessage | Command\[Any\]</code> – the planner has spent its retry budget.
