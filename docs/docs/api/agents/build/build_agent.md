---
title: agrag.agents.build.build_agent
sidebar_label: build_agent
---

# `agrag.agents.build.build_agent` \{#agrag-agents-build-build_agent}

```python
build_agent(*, graph_store:GraphStore, embedder:Embedder, scope:frozenset[str], project_id:str, agent_id:str, llm_settings:AgentLLMSettings, agent_settings:AgentSettings | None = None, vector_store:VectorStore | None = None, tracer:Tracer | None = None) -> Any
```

Build one agent bound to trusted document and memory scopes.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Store used by evidence and memory operations.
- **embedder** (<code>[Embedder](../../embedding/base/Embedder.md)</code>) – Embedder used for semantic evidence search.
- **scope** (<code>frozenset\[str\]</code>) – Document keys the agent may read.
- **project_id** (<code>str</code>) – Trusted project identifier for task and decision memory.
- **agent_id** (<code>str</code>) – Trusted author identifier for memory writes.
- **llm_settings** (<code>[AgentLLMSettings](../settings/AgentLLMSettings.md)</code>) – Model configuration and composition strategy.
- **agent_settings** (<code>[AgentSettings](../settings/AgentSettings.md) | None</code>) – Run limits. Defaults to environment settings.
- **vector_store** (<code>[VectorStore](../../vectordb/base/VectorStore.md) | None</code>) – Optional external store for evidence search.
- **tracer** (<code>Tracer | None</code>) – Optional OpenTelemetry tracer for agent and model calls.

**Returns:**

- <code>Any</code> – An agent with `ainvoke({"task_name": ..., "question": ...})`.

**Raises:**

- <code>[AgentMissingExtraError](../errors/AgentMissingExtraError.md)</code> – The `agents` extra is not installed, or
  tracing was requested without the `observability` extra.
