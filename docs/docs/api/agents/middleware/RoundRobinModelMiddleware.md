---
title: agrag.agents.middleware.RoundRobinModelMiddleware
sidebar_label: RoundRobinModelMiddleware
---

# `agrag.agents.middleware.RoundRobinModelMiddleware` \{#agrag-agents-middleware-RoundRobinModelMiddleware}

```python
RoundRobinModelMiddleware(models:list[Any]) -> None
```

Bases: <code>AgentMiddleware</code>

Rotate across the configured chat models, one model per call.

Overrides the request's model on every model call so requests are
distributed across all configured clients in order.

**Functions:**

- [**awrap_model_call**](#agrag-agents-middleware-RoundRobinModelMiddleware-awrap_model_call) – Run the call against the next model in rotation.
- [**wrap_model_call**](#agrag-agents-middleware-RoundRobinModelMiddleware-wrap_model_call) – Run the call against the next model in rotation.

**Parameters:**

- **models** (<code>list\[Any\]</code>) – Chat models to rotate across, in configuration
  order. Must be non-empty.

**Raises:**

- <code>ValueError</code> – models is empty.

## `awrap_model_call` \{#agrag-agents-middleware-RoundRobinModelMiddleware-awrap_model_call}

```python
awrap_model_call(request:ModelRequest, handler:Callable[[ModelRequest], Awaitable[ModelResponse]]) -> Any
```

Run the call against the next model in rotation.

## `wrap_model_call` \{#agrag-agents-middleware-RoundRobinModelMiddleware-wrap_model_call}

```python
wrap_model_call(request:ModelRequest, handler:Callable[[ModelRequest], ModelResponse]) -> Any
```

Run the call against the next model in rotation.
