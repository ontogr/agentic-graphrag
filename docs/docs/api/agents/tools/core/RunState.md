---
title: agrag.agents.tools.core.RunState
sidebar_label: RunState
---

# `agrag.agents.tools.core.RunState` \{#agrag-agents-tools-core-RunState}

```python
RunState(max_tool_calls:int, tool_calls:int = 0, budget_exhausted:bool = False, recording_failed:bool = False, retrieval_failed:bool = False, fetched_ids:list[str] = list(), fetches:dict[str, Any] = dict()) -> None
```

Mutable facts accumulated by tools during one agent run.

**Attributes:**

- [**budget_exhausted**](#agrag-agents-tools-core-RunState-budget_exhausted) (<code>bool</code>) –
- [**fetched_ids**](#agrag-agents-tools-core-RunState-fetched_ids) (<code>list\[str\]</code>) –
- [**fetches**](#agrag-agents-tools-core-RunState-fetches) (<code>dict\[str, Any\]</code>) –
- [**max_tool_calls**](#agrag-agents-tools-core-RunState-max_tool_calls) (<code>int</code>) –
- [**recording_failed**](#agrag-agents-tools-core-RunState-recording_failed) (<code>bool</code>) –
- [**retrieval_failed**](#agrag-agents-tools-core-RunState-retrieval_failed) (<code>bool</code>) –
- [**tool_calls**](#agrag-agents-tools-core-RunState-tool_calls) (<code>int</code>) –

## `budget_exhausted` \{#agrag-agents-tools-core-RunState-budget_exhausted}

```python
budget_exhausted: bool = False
```

## `fetched_ids` \{#agrag-agents-tools-core-RunState-fetched_ids}

```python
fetched_ids: list[str] = field(default_factory=list)
```

## `fetches` \{#agrag-agents-tools-core-RunState-fetches}

```python
fetches: dict[str, Any] = field(default_factory=dict)
```

## `max_tool_calls` \{#agrag-agents-tools-core-RunState-max_tool_calls}

```python
max_tool_calls: int
```

## `recording_failed` \{#agrag-agents-tools-core-RunState-recording_failed}

```python
recording_failed: bool = False
```

## `retrieval_failed` \{#agrag-agents-tools-core-RunState-retrieval_failed}

```python
retrieval_failed: bool = False
```

## `tool_calls` \{#agrag-agents-tools-core-RunState-tool_calls}

```python
tool_calls: int = 0
```
