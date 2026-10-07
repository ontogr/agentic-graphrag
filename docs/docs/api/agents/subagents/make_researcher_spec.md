---
title: agrag.agents.subagents.make_researcher_spec
sidebar_label: make_researcher_spec
---

# `agrag.agents.subagents.make_researcher_spec` \{#agrag-agents-subagents-make_researcher_spec}

```python
make_researcher_spec(tools:list[Any], middleware:list[Any], schema:GraphSchema) -> dict[str, Any]
```

Build the researcher subagent spec.

**Parameters:**

- **tools** (<code>list\[Any\]</code>) – The tools this subagent may call.
- **middleware** (<code>list\[Any\]</code>) – Middleware for this subagent's own model calls. Not
  inherited from the parent agent -- DeepAgents reads only this
  key for an isolated-mode subagent, never the top-level agent's
  own middleware.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – Fills the compact schema summary into RESEARCHER_SYSTEM.

**Returns:**

- <code>dict\[str, Any\]</code> – A SubAgent-shaped dict for create_deep_agent's subagents= list.
