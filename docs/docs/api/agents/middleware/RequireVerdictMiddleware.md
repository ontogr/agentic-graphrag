---
title: agrag.agents.middleware.RequireVerdictMiddleware
sidebar_label: RequireVerdictMiddleware
---

# `agrag.agents.middleware.RequireVerdictMiddleware` \{#agrag-agents-middleware-RequireVerdictMiddleware}

```python
RequireVerdictMiddleware(max_reminders:int = 2) -> None
```

Bases: <code>AgentMiddleware</code>

Ask again when the verifier answers in prose instead of with its verdict.

A subagent that has tools stops as soon as the model replies without a tool
call, even when the reply is not the structured response. The planner then
reads prose where it expects a `VerificationResult`. This middleware sends a
short reminder and calls the model again, up to `max_reminders` times in one
subagent run, and then lets the run end as before.

**Functions:**

- [**after_model**](#agrag-agents-middleware-RequireVerdictMiddleware-after_model) – Send a reminder and jump back to the model after a prose reply.

**Parameters:**

- **max_reminders** (<code>int</code>) – How many reminders one subagent run may send.

## `after_model` \{#agrag-agents-middleware-RequireVerdictMiddleware-after_model}

```python
after_model(state:Any, runtime:Any) -> dict[str, Any] | None
```

Send a reminder and jump back to the model after a prose reply.

**Parameters:**

- **state** (<code>Any</code>) – The current agent state.
- **runtime** (<code>Any</code>) – The LangChain middleware runtime.

**Returns:**

- <code>dict\[str, Any\] | None</code> – A reminder and model jump, or `None` when no retry is needed.
