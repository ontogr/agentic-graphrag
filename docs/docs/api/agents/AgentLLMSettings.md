---
title: agrag.agents.AgentLLMSettings
sidebar_label: AgentLLMSettings
---

# `agrag.agents.AgentLLMSettings` \{#agrag-agents-AgentLLMSettings}

Bases: <code>BaseSettings</code>

LLM client config for the agent's own reasoning turns.

Mirrors ExtractionLLMSettings for the agent role: same shape,
same from_openai_compatible_env() convention, because the
agent's model and the extraction model are configured the same
way even though the agent calls its model through LangChain,
not BAML.

**Attributes:**

- [**clients**](#agrag-agents-AgentLLMSettings-clients) (<code>list\[LLMClientConfig\]</code>) – The LLM client(s) to use. One element for a single
  provider; more than one composed per strategy through
  agent middleware.
- [**strategy**](#agrag-agents-AgentLLMSettings-strategy) (<code>Literal['single', 'fallback', 'round_robin']</code>) – How to compose multiple clients. `"fallback"`
  tries the other clients in order when a model call fails;
  `"round_robin"` rotates across all clients per call.
  Ignored with one client.

Env prefix: `AGENT_LLM_`.

**Functions:**

- [**from_openai_compatible_env**](#agrag-agents-AgentLLMSettings-from_openai_compatible_env) – Build settings from OpenAI-compatible env vars.

## `clients` \{#agrag-agents-AgentLLMSettings-clients}

```python
clients: list[LLMClientConfig]
```

## `from_openai_compatible_env` \{#agrag-agents-AgentLLMSettings-from_openai_compatible_env}

```python
from_openai_compatible_env() -> AgentLLMSettings
```

Build settings from OpenAI-compatible env vars.

Loads `.env` first, then reads `AGENT_LLM_BASE_URL`,
`AGENT_LLM_API_KEY`, and `AGENT_LLM_MODEL_ID`. When the
agent-specific variables are unset, the shared `LLM_*`
convenience variables used by the extraction role stand in, so
one `.env` can configure every LLM-backed role. The model
name defaults to `gpt-4o-mini` when neither variable names
one.

**Returns:**

- <code>[AgentLLMSettings](settings/AgentLLMSettings.md)</code> – AgentLLMSettings with one openai-generic client.

## `model_config` \{#agrag-agents-AgentLLMSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='AGENT_LLM_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

## `strategy` \{#agrag-agents-AgentLLMSettings-strategy}

```python
strategy: Literal['single', 'fallback', 'round_robin'] = 'single'
```
