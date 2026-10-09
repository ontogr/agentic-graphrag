---
title: agrag.observability.get_tracer
sidebar_label: get_tracer
---

# `agrag.observability.get_tracer` \{#agrag-observability-get_tracer}

```python
get_tracer(tracer:Tracer | None) -> Tracer
```

Return a usable tracer.

**Parameters:**

- **tracer** (<code>Tracer | None</code>) – A caller-supplied tracer, or `None` for an explicit no-op tracer.

**Returns:**

- <code>Tracer</code> – agrag uses the supplied tracer or a no-op for `None` and skips global tracing.
