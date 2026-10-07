---
title: agrag.agents.settings.AgentSettings
sidebar_label: AgentSettings
---

# `agrag.agents.settings.AgentSettings` \{#agrag-agents-settings-AgentSettings}

Bases: <code>BaseSettings</code>

Configuration for the agent loop itself.

**Attributes:**

- [**recursion_limit**](#agrag-agents-settings-AgentSettings-recursion_limit) (<code>int</code>) – The maximum LangGraph step count before
  the loop stops and reports incomplete progress.
  Env: `AGENT_RECURSION_LIMIT`.
- [**max_research_attempts**](#agrag-agents-settings-AgentSettings-max_research_attempts) (<code>int</code>) – The maximum number of times the
  planner may re-delegate to the researcher after
  receiving `INSUFFICIENT` from the verifier. The
  planner's initial decomposition into sub-questions is
  not bounded by this field; the LangGraph recursion
  limit remains the backstop for that pass.
  Env: `AGENT_MAX_RESEARCH_ATTEMPTS`.

Env prefix: `AGENT_`.

## `max_research_attempts` \{#agrag-agents-settings-AgentSettings-max_research_attempts}

```python
max_research_attempts: int = 3
```

## `model_config` \{#agrag-agents-settings-AgentSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='AGENT_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

## `recursion_limit` \{#agrag-agents-settings-AgentSettings-recursion_limit}

```python
recursion_limit: int = 50
```
