---
title: agrag.eval.trajectory.Step
sidebar_label: Step
---

# `agrag.eval.trajectory.Step` \{#agrag-eval-trajectory-Step}

Bases: <code>BaseModel</code>

One tool or model step of an agent run.

**Attributes:**

- [**kind**](#agrag-eval-trajectory-Step-kind) (<code>Literal['tool', 'llm']</code>) – `"tool"` for a tool call, `"llm"` for a model call.
- [**name**](#agrag-eval-trajectory-Step-name) (<code>str</code>) – The tool name, or the span name for a model call.
- [**args**](#agrag-eval-trajectory-Step-args) (<code>dict\[str, Any\]</code>) – The parsed `input.value` span attribute.
- [**output**](#agrag-eval-trajectory-Step-output) (<code>str</code>) – The step's output text, unwrapped from its tool message.
- [**span_id**](#agrag-eval-trajectory-Step-span_id) (<code>str</code>) – The span id as hex.
- [**parent_ids**](#agrag-eval-trajectory-Step-parent_ids) (<code>list\[str\]</code>) – The ancestor span ids, nearest first, as hex.
- [**started**](#agrag-eval-trajectory-Step-started) (<code>int</code>) – Start time in nanoseconds.
- [**ended**](#agrag-eval-trajectory-Step-ended) (<code>int</code>) – End time in nanoseconds.
- [**subagent**](#agrag-eval-trajectory-Step-subagent) (<code>str | None</code>) – The `subagent_type` of the nearest ancestor `task`
  span, or None for a planner step.

## `args` \{#agrag-eval-trajectory-Step-args}

```python
args: dict[str, Any]
```

## `ended` \{#agrag-eval-trajectory-Step-ended}

```python
ended: int
```

## `kind` \{#agrag-eval-trajectory-Step-kind}

```python
kind: Literal['tool', 'llm']
```

## `name` \{#agrag-eval-trajectory-Step-name}

```python
name: str
```

## `output` \{#agrag-eval-trajectory-Step-output}

```python
output: str
```

## `parent_ids` \{#agrag-eval-trajectory-Step-parent_ids}

```python
parent_ids: list[str]
```

## `span_id` \{#agrag-eval-trajectory-Step-span_id}

```python
span_id: str
```

## `started` \{#agrag-eval-trajectory-Step-started}

```python
started: int
```

## `subagent` \{#agrag-eval-trajectory-Step-subagent}

```python
subagent: str | None
```
