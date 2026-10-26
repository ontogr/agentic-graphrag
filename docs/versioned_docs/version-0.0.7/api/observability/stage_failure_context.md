---
title: agrag.observability.stage_failure_context
sidebar_label: stage_failure_context
---

# `agrag.observability.stage_failure_context` \{#agrag-observability-stage_failure_context}

```python
stage_failure_context() -> tuple[str | None, str | None]
```

Return the current span's trace and span id as hex, or (None, None).

Reads whatever span is ambiently current. Returns `(None, None)` when
that span is not being recorded -- true when no span is open, when the
current span came from `get_tracer(None)`'s no-op tracer (even one
wrapping a real ambient context for correct propagation -- see the
module-level note above), and when a real tracer's sampler dropped the
span. Uses `is_recording()`, not the span context's `is_valid`: a
no-op tracer's span can carry a *valid* context (a real host trace id it
is merely propagating, not recording into) without this function ever
exposing that id.
