---
title: agrag.agents.model.build_model_middleware
sidebar_label: build_model_middleware
---

# `agrag.agents.model.build_model_middleware` \{#agrag-agents-model-build_model_middleware}

```python
build_model_middleware(clients:list[LLMClientConfig], *, strategy:Literal['single', 'fallback', 'round_robin'] = 'single') -> list[Any]
```

Build agent middleware composing multiple clients per strategy.

The agent calls `clients[0]` as its primary model. With more than
one client, the returned middleware teaches the agent loop to use
the rest: `"fallback"` tries the other clients in order when the
primary model call fails, and `"round_robin"` rotates across
every client per model call.

**Parameters:**

- **clients** (<code>list\[LLMClientConfig\]</code>) – The configured clients, in priority order.
- **strategy** (<code>Literal['single', 'fallback', 'round_robin']</code>) – How to compose `clients`. `"single"` ignores all
  but the first client.

**Returns:**

- <code>list\[Any\]</code> – Middleware for create_deep_agent/create_agent; empty when there
- <code>list\[Any\]</code> – is nothing to compose.

**Raises:**

- <code>[UnsupportedAgentProviderError](UnsupportedAgentProviderError.md)</code> – a client's provider has no
  agent-side mapping.
