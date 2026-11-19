---
title: agrag.agents.tracing.require_tracing
sidebar_label: require_tracing
---

# `agrag.agents.tracing.require_tracing` \{#agrag-agents-tracing-require_tracing}

```python
require_tracing() -> None
```

Raise a typed error when tracing dependencies are unavailable.

**Raises:**

- <code>[AgentMissingExtraError](../errors/AgentMissingExtraError.md)</code> – The `observability` extra is not installed.
- <code>ImportError</code> – The installed OpenInference package has an incompatible
  layout.
