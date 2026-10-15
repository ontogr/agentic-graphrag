---
title: agrag.agents
sidebar_position: 2
---


# `agrag.agents` \{#agrag-agents}

Agentic layer: one task-scoped evidence agent over the graph.

`build_agent` is imported lazily because it needs the optional `agents`
extra. Importing this package does not require that extra.

**Modules:**

- [**build**](build/index.md) – Build the single task-scoped evidence agent.
- [**errors**](errors/index.md) – Errors raised by the agent layer.
- [**harness**](harness/index.md) – Process-global DeepAgents harness profile registration.
- [**ledger**](ledger/index.md) – Citation ledger: assigns and tracks stable keys for one agent run.
- [**middleware**](middleware/index.md) – Middleware for composing configured chat models.
- [**model**](model/index.md) – Translate LLMClientConfig into the matching LangChain chat model.
- [**prompts**](prompts/index.md) – The single default agent prompt.
- [**result**](result/index.md) – Typed result returned after a task-scoped agent run.
- [**settings**](settings/index.md) – Env-backed LLM and loop config for the agent layer.
- [**tools**](tools/index.md) – Agent tools: thin wrappers calling SearchEngine with fixed Recipes.
- [**tracing**](tracing/index.md) – Per-run OpenInference tracing for agent runs.
- [**verification**](verification/index.md) – The structured verdict of the fixed-input verifier.

**Classes:**

- [**AgentLLMSettings**](settings/AgentLLMSettings.md) – LLM client config for the agent's own reasoning turns.
- [**AgentMissingExtraError**](errors/AgentMissingExtraError.md) – Agent tracing needs a package extra that is not installed.
- [**AgentRunResult**](result/AgentRunResult.md) – Outcome, answer, evidence references and conversation for one run.
- [**AgentSettings**](settings/AgentSettings.md) – Configuration for the agent loop itself.
- [**Ledger**](ledger/Ledger-ref.md) – Assigns and tracks stable citation keys for one agent run.

**Functions:**

- [**build_agent**](build/build_agent.md) – Build one agent bound to trusted document and memory scopes.
