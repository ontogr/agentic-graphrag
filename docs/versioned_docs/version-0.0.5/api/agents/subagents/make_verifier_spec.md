---
title: agrag.agents.subagents.make_verifier_spec
sidebar_label: make_verifier_spec
---

# `agrag.agents.subagents.make_verifier_spec` \{#agrag-agents-subagents-make_verifier_spec}

```python
make_verifier_spec(middleware:list[Any]) -> dict[str, Any]
```

Build the verifier subagent spec.

**Parameters:**

- **middleware** (<code>list\[Any\]</code>) – Middleware for this subagent's own model calls. Not
  inherited from the parent agent -- DeepAgents reads only this
  key for an isolated-mode subagent, never the top-level agent's
  own middleware.

**Returns:**

- <code>dict\[str, Any\]</code> – A SubAgent-shaped dict for create_deep_agent's subagents= list.
- <code>dict\[str, Any\]</code> – tools is the explicit empty list, not omitted -- an omitted key
- <code>dict\[str, Any\]</code> – would inherit the parent's tools instead of granting none. The
- <code>dict\[str, Any\]</code> – filesystem tools DeepAgents adds are hidden, and a reply without a
- <code>dict\[str, Any\]</code> – `VerificationResult` is met with a reminder.
