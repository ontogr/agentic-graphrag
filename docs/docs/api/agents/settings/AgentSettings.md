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
- [**max_tool_calls**](#agrag-agents-settings-AgentSettings-max_tool_calls) (<code>int</code>) – Maximum number of tool calls in one task run.
  Env: `AGENT_MAX_TOOL_CALLS`.
- [**max_result_characters**](#agrag-agents-settings-AgentSettings-max_result_characters) (<code>int</code>) – Maximum text returned by one evidence fetch.
  Env: `AGENT_MAX_RESULT_CHARACTERS`.

Env prefix: `AGENT_`.

## `max_result_characters` \{#agrag-agents-settings-AgentSettings-max_result_characters}

```python
max_result_characters: int = Field(default=12000, ge=1)
```

## `max_tool_calls` \{#agrag-agents-settings-AgentSettings-max_tool_calls}

```python
max_tool_calls: int = Field(default=20, ge=1)
```

## `model_config` \{#agrag-agents-settings-AgentSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='AGENT_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

## `recursion_limit` \{#agrag-agents-settings-AgentSettings-recursion_limit}

```python
recursion_limit: int = Field(default=50, ge=1)
```
