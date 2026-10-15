---
title: agrag.agents.middleware.TaskEventMiddleware
sidebar_label: TaskEventMiddleware
---

# `agrag.agents.middleware.TaskEventMiddleware` \{#agrag-agents-middleware-TaskEventMiddleware}

```python
TaskEventMiddleware(memory:Any, task_name:str, run_state:Any) -> None
```

Bases: <code>AgentMiddleware</code>

Persist assistant messages as the model produces them.

**Functions:**

- [**awrap_model_call**](#agrag-agents-middleware-TaskEventMiddleware-awrap_model_call) – Record the assistant response before any tool it requests runs.

## `awrap_model_call` \{#agrag-agents-middleware-TaskEventMiddleware-awrap_model_call}

```python
awrap_model_call(request:ModelRequest, handler:Callable[[ModelRequest], Awaitable[ModelResponse]]) -> ModelResponse
```

Record the assistant response before any tool it requests runs.
