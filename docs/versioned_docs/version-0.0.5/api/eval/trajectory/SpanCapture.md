---
title: agrag.eval.trajectory.SpanCapture
sidebar_label: SpanCapture
---

# `agrag.eval.trajectory.SpanCapture` \{#agrag-eval-trajectory-SpanCapture}

```python
SpanCapture() -> None
```

Capture one agent run's spans for `read_trajectory`.

Use as a context manager around `agent.ainvoke` and read the run with
`trajectory()` after. Each capture has its own provider and exporter,
so captures never share spans and the global provider is unchanged.

<details open>
<summary>Example</summary>

```python
with SpanCapture() as capture:
    agent = build_agent(engine, settings, tracer=capture.tracer)
    result = await agent.ainvoke({"messages": [...]})
trajectory = capture.trajectory()
```

</details>

**Functions:**

- [**trajectory**](#agrag-eval-trajectory-SpanCapture-trajectory) – Read the captured spans as a trajectory.

**Attributes:**

- [**tracer**](#agrag-eval-trajectory-SpanCapture-tracer) (<code>Tracer</code>) – The tracer to pass as `tracer=` to `build_agent`.

## `tracer` \{#agrag-eval-trajectory-SpanCapture-tracer}

```python
tracer: Tracer
```

The tracer to pass as `tracer=` to `build_agent`.

**Returns:**

- <code>Tracer</code> – A tracer bound to this capture's private provider.

## `trajectory` \{#agrag-eval-trajectory-SpanCapture-trajectory}

```python
trajectory() -> Trajectory
```

Read the captured spans as a trajectory.

**Returns:**

- <code>[Trajectory](Trajectory-ref.md)</code> – The trajectory read from the spans captured so far.
