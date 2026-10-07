---
title: agrag.agents.middleware.HideToolsMiddleware
sidebar_label: HideToolsMiddleware
---

# `agrag.agents.middleware.HideToolsMiddleware` \{#agrag-agents-middleware-HideToolsMiddleware}

```python
HideToolsMiddleware(names:frozenset[str]) -> None
```

Bases: <code>AgentMiddleware</code>

Remove tools by name from every model request.

DeepAgents gives each subagent its filesystem tools, even when the spec
lists none. A role that needs no tools, such as the verifier, hides them so
the model can only answer through its structured output.

**Functions:**

- [**awrap_model_call**](#agrag-agents-middleware-HideToolsMiddleware-awrap_model_call) – Run the call with the named tools removed from the request.

**Parameters:**

- **names** (<code>frozenset\[str\]</code>) – The tool names to remove.

## `awrap_model_call` \{#agrag-agents-middleware-HideToolsMiddleware-awrap_model_call}

```python
awrap_model_call(request:ModelRequest, handler:Callable[[ModelRequest], Awaitable[ModelResponse]]) -> Any
```

Run the call with the named tools removed from the request.

**Parameters:**

- **request** (<code>ModelRequest</code>) – The intercepted model request.
- **handler** (<code>Callable\\[[ModelRequest\], Awaitable\[ModelResponse\]\]</code>) – The remaining model-call pipeline.

**Returns:**

- <code>Any</code> – The handler's model response.
