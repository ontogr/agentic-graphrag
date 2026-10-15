---
title: agrag.agents.middleware.RunState
sidebar_label: RunState
---

# `agrag.agents.middleware.RunState` \{#agrag-agents-middleware-RunState}

```python
RunState(max_tool_calls:int, tool_calls:int = 0, budget_exhausted:bool = False, recording_failed:bool = False, recording_failures:list[str] = list(), retrieval_failed:bool = False, fetched_ids:list[str] = list(), fetches:dict[str, Any] = dict()) -> None
```

Mutable facts accumulated by tools and middleware during one run.

**Attributes:**

- [**max_tool_calls**](#agrag-agents-middleware-RunState-max_tool_calls) (<code>int</code>) – Tool calls allowed in the run.
- [**tool_calls**](#agrag-agents-middleware-RunState-tool_calls) (<code>int</code>) – Tool calls admitted so far.
- [**budget_exhausted**](#agrag-agents-middleware-RunState-budget_exhausted) (<code>bool</code>) – Whether the run reached its tool-call bound.
- [**recording_failed**](#agrag-agents-middleware-RunState-recording_failed) (<code>bool</code>) – Whether an event or decision write did not complete.
- [**recording_failures**](#agrag-agents-middleware-RunState-recording_failures) (<code>list\[str\]</code>) – Descriptions of the writes that did not complete.
- [**retrieval_failed**](#agrag-agents-middleware-RunState-retrieval_failed) (<code>bool</code>) – Whether a search leg failed or a result was truncated.
- [**fetched_ids**](#agrag-agents-middleware-RunState-fetched_ids) (<code>list\[str\]</code>) – Evidence ids fetched in this run with complete text.
- [**fetches**](#agrag-agents-middleware-RunState-fetches) (<code>dict\[str, Any\]</code>) – Fetch outcomes by evidence id.

**Functions:**

- [**fail_recording**](#agrag-agents-middleware-RunState-fail_recording) – Mark that a write did not complete and keep its description.

## `budget_exhausted` \{#agrag-agents-middleware-RunState-budget_exhausted}

```python
budget_exhausted: bool = False
```

## `fail_recording` \{#agrag-agents-middleware-RunState-fail_recording}

```python
fail_recording(description:str) -> None
```

Mark that a write did not complete and keep its description.

## `fetched_ids` \{#agrag-agents-middleware-RunState-fetched_ids}

```python
fetched_ids: list[str] = field(default_factory=list)
```

## `fetches` \{#agrag-agents-middleware-RunState-fetches}

```python
fetches: dict[str, Any] = field(default_factory=dict)
```

## `max_tool_calls` \{#agrag-agents-middleware-RunState-max_tool_calls}

```python
max_tool_calls: int
```

## `recording_failed` \{#agrag-agents-middleware-RunState-recording_failed}

```python
recording_failed: bool = False
```

## `recording_failures` \{#agrag-agents-middleware-RunState-recording_failures}

```python
recording_failures: list[str] = field(default_factory=list)
```

## `retrieval_failed` \{#agrag-agents-middleware-RunState-retrieval_failed}

```python
retrieval_failed: bool = False
```

## `tool_calls` \{#agrag-agents-middleware-RunState-tool_calls}

```python
tool_calls: int = 0
```
