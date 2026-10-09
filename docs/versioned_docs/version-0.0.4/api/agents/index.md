---
title: agrag.agents
sidebar_position: 2
---


# `agrag.agents` \{#agrag-agents}

Agentic layer: planner/researcher/verifier over SearchEngine.

`build_agent` lives in `agrag.agents.build` and is not re-exported here: it needs
the `agents` extra to import, and this package must import on a base install.

**Modules:**

- [**build**](build/index.md) – Build the planner/researcher/verifier agent graph.
- [**errors**](errors/index.md) – Errors raised by the agent layer.
- [**harness**](harness/index.md) – Process-global DeepAgents harness profile registration.
- [**ledger**](ledger/index.md) – Citation ledger: assigns and tracks stable keys for one agent run.
- [**middleware**](middleware/index.md) – Agent middleware for composing models and bounding the research loop.
- [**model**](model/index.md) – Translate LLMClientConfig into the matching LangChain chat model.
- [**prompts**](prompts/index.md) – Agent prompt templates for planner, researcher, verifier, and fallback.
- [**result**](result/index.md) – Result type returned by an agent run.
- [**settings**](settings/index.md) – Env-backed LLM and loop config for the agent layer.
- [**subagents**](subagents/index.md) – Subagent specs for the researcher and verifier roles.
- [**tools**](tools/index.md) – Agent tools: thin wrappers calling SearchEngine with fixed Recipes.
- [**tracing**](tracing/index.md) – Per-run OpenInference tracing for agent runs.
- [**verification**](verification/index.md) – The verifier subagent's structured verdict.

**Classes:**

- [**AgentLLMSettings**](settings/AgentLLMSettings.md) – LLM client config for the agent's own reasoning turns.
- [**AgentMissingExtraError**](errors/AgentMissingExtraError.md) – Agent tracing needs a package extra that is not installed.
- [**AgentRunResult**](result/AgentRunResult.md) – Result of one agent run.
- [**AgentSettings**](settings/AgentSettings.md) – Configuration for the agent loop itself.
- [**Ledger**](ledger/Ledger-ref.md) – Assigns and tracks stable citation keys for one agent run.
