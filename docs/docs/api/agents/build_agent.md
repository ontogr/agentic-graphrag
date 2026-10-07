---
title: agrag.agents.build_agent
sidebar_label: build_agent
---

# `agrag.agents.build_agent` \{#agrag-agents-build_agent}

```python
build_agent(*, engine:SearchEngine, llm_settings:AgentLLMSettings, agent_settings:AgentSettings | None = None, filters:SearchFilters | None = None, graph_schema:GraphSchema | None = None, tracer:Tracer | None = None) -> Any
```

Build the planner/researcher/verifier agent graph.

Constructs a LangGraph-based agent with three roles:
planner (decomposes the question), researcher (has tools),
and verifier (judges evidence sufficiency and returns a
structured verdict).

Each call to `ainvoke` creates a fresh `Ledger` so
citation numbering, identity mappings, and retrieved evidence
do not leak across runs, and a fresh `ResearchAttemptLimiter`
so one question's retry budget does not spend another's.

**Parameters:**

- **engine** (<code>[SearchEngine](../retrieval/search_engine/SearchEngine.md)</code>) – Retrieval to expose to the researcher subagent's
  tools.
- **llm_settings** (<code>[AgentLLMSettings](settings/AgentLLMSettings.md)</code>) – The model every subagent role calls, via
  build_chat_model. With several clients, the remaining
  ones compose per strategy through agent middleware.
- **agent_settings** (<code>[AgentSettings](settings/AgentSettings.md) | None</code>) – Loop-level configuration; defaults from
  environment. The recursion limit is enforced as the
  LangGraph `recursion_limit` in the invoke config, and
  `max_research_attempts` bounds how many times the
  planner may re-research after an INSUFFICIENT verdict.
- **filters** (<code>[SearchFilters](../retrieval/filters/SearchFilters.md) | None</code>) – Retrieval scope applied to every tool search,
  e.g. document or tenant constraints. None searches
  unfiltered. A non-empty scope also removes the
  `query_graph_directly` tool, since a generated query
  cannot be confined to a scope.
- **graph_schema** (<code>[GraphSchema](../common/data_models/graph_schema/GraphSchema.md) | None</code>) – The schema the researcher prompt and the
  `query_graph_directly` tool describe. None uses the
  engine's own resolved schema; a value that differs from
  the engine's raises, so the prompt cannot describe a
  graph the engine does not search.
- **tracer** (<code>Tracer | None</code>) – Receives OpenInference spans for every `ainvoke`,
  including the researcher and verifier subagents' tool and
  model calls. None emits no spans. Spans carry the question,
  tool inputs, and evidence text.

**Returns:**

- <code>Any</code> – An agent whose `ainvoke` returns an `AgentRunResult`: the
- <code>Any</code> – run's `messages` plus its `ledger`, which maps each
- <code>Any</code> – citation key in the answer back to its evidence. When
- <code>Any</code> – deepagents is not installed, a single-search-plus-synthesis
- <code>Any</code> – fallback with the same result shape.

**Raises:**

- <code>[AgentMissingExtraError](errors/AgentMissingExtraError.md)</code> – `tracer` is set but the `observability`
  extra is not installed.
- <code>ValueError</code> – `graph_schema` differs from the engine's schema.
