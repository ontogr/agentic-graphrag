---
title: agrag.agents.middleware.TaskEventMiddleware
sidebar_label: TaskEventMiddleware
---

# `agrag.agents.middleware.TaskEventMiddleware` \{#agrag-agents-middleware-TaskEventMiddleware}

```python
TaskEventMiddleware(memory:Any, task_name:str, run_state:RunState) -> None
```

Bases: <code>AgentMiddleware</code>

Persist assistant messages, tool calls and tool results as task events.

A tool that raises does not end the run. Its error is recorded as the tool
result, the steps this run left in progress are marked failed, and the
model receives an error tool message so it can react.

**Functions:**

- [**awrap_model_call**](#agrag-agents-middleware-TaskEventMiddleware-awrap_model_call) – Record the assistant response before any tool it requests runs.
- [**awrap_tool_call**](#agrag-agents-middleware-TaskEventMiddleware-awrap_tool_call) – Record a tool call, then its result or the error that replaced it.

## `awrap_model_call` \{#agrag-agents-middleware-TaskEventMiddleware-awrap_model_call}

```python
awrap_model_call(request:ModelRequest, handler:Callable[[ModelRequest], Awaitable[ModelResponse]]) -> ModelResponse
```

Record the assistant response before any tool it requests runs.

## `awrap_tool_call` \{#agrag-agents-middleware-TaskEventMiddleware-awrap_tool_call}

```python
awrap_tool_call(request:Any, handler:Callable[[Any], Awaitable[Any]]) -> Any
```

Record a tool call, then its result or the error that replaced it.
