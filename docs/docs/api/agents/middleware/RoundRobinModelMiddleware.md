---
title: agrag.agents.middleware.RoundRobinModelMiddleware
sidebar_label: RoundRobinModelMiddleware
---

# `agrag.agents.middleware.RoundRobinModelMiddleware` \{#agrag-agents-middleware-RoundRobinModelMiddleware}

```python
RoundRobinModelMiddleware(models:list[Any]) -> None
```

Bases: <code>AgentMiddleware</code>

Rotate model requests across configured clients.

**Functions:**

- [**awrap_model_call**](#agrag-agents-middleware-RoundRobinModelMiddleware-awrap_model_call) – Invoke the next model in the rotation asynchronously.
- [**wrap_model_call**](#agrag-agents-middleware-RoundRobinModelMiddleware-wrap_model_call) – Invoke the next model in the rotation.

## `awrap_model_call` \{#agrag-agents-middleware-RoundRobinModelMiddleware-awrap_model_call}

```python
awrap_model_call(request:ModelRequest, handler:Callable[[ModelRequest], Awaitable[ModelResponse]]) -> Any
```

Invoke the next model in the rotation asynchronously.

## `wrap_model_call` \{#agrag-agents-middleware-RoundRobinModelMiddleware-wrap_model_call}

```python
wrap_model_call(request:ModelRequest, handler:Callable[[ModelRequest], ModelResponse]) -> Any
```

Invoke the next model in the rotation.
