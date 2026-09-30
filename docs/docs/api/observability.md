---
title: agrag.observability
sidebar_position: 10
---

## `agrag.observability` \{#agrag-observability}

OpenTelemetry wiring for the ingestion layer.

This module imports only `opentelemetry-api`. The SDK and exporters stay in
the optional `observability` extra and are never imported here; a caller
wires them before opening a graph. The tracer is constructor-injected, never
ambient: `get_tracer(None)` returns an explicit no-op tracer instead of
reaching the global `TracerProvider`.

**Functions:**

- [**get_tracer**](#agrag-observability-get_tracer) – Return a usable tracer.
- [**record_stage_failure**](#agrag-observability-record_stage_failure) – Record `exc` as an error on the current span, then return its ids.
- [**record_swallowed_exception**](#agrag-observability-record_swallowed_exception) – Record `exc` on the current span without marking it errored.
- [**stage_failure_context**](#agrag-observability-stage_failure_context) – Return the current span's trace and span id as hex, or (None, None).

**Attributes:**

- [**DB_COLLECTION_NAME**](#agrag-observability-DB_COLLECTION_NAME) –
- [**DB_NAMESPACE**](#agrag-observability-DB_NAMESPACE) –
- [**DB_OPERATION_BATCH_SIZE**](#agrag-observability-DB_OPERATION_BATCH_SIZE) –
- [**DB_QUERY_PARAMETER_PREFIX**](#agrag-observability-DB_QUERY_PARAMETER_PREFIX) –
- [**DB_QUERY_TEXT**](#agrag-observability-DB_QUERY_TEXT) –
- [**DB_SYSTEM_NAME**](#agrag-observability-DB_SYSTEM_NAME) –

### `agrag.observability.DB_COLLECTION_NAME` \{#agrag-observability-DB_COLLECTION_NAME}

```python
DB_COLLECTION_NAME = 'db.collection.name'
```

### `agrag.observability.DB_NAMESPACE` \{#agrag-observability-DB_NAMESPACE}

```python
DB_NAMESPACE = 'db.namespace'
```

### `agrag.observability.DB_OPERATION_BATCH_SIZE` \{#agrag-observability-DB_OPERATION_BATCH_SIZE}

```python
DB_OPERATION_BATCH_SIZE = 'db.operation.batch.size'
```

### `agrag.observability.DB_QUERY_PARAMETER_PREFIX` \{#agrag-observability-DB_QUERY_PARAMETER_PREFIX}

```python
DB_QUERY_PARAMETER_PREFIX = 'db.query.parameter.'
```

### `agrag.observability.DB_QUERY_TEXT` \{#agrag-observability-DB_QUERY_TEXT}

```python
DB_QUERY_TEXT = 'db.query.text'
```

### `agrag.observability.DB_SYSTEM_NAME` \{#agrag-observability-DB_SYSTEM_NAME}

```python
DB_SYSTEM_NAME = 'db.system.name'
```

### `agrag.observability.get_tracer` \{#agrag-observability-get_tracer}

```python
get_tracer(tracer:Tracer | None) -> Tracer
```

Return a usable tracer.

**Parameters:**

- **tracer** (<code>Tracer | None</code>) – A caller-supplied tracer, or `None` for an explicit no-op tracer.

**Returns:**

- <code>Tracer</code> – agrag uses the supplied tracer or a no-op for `None` and skips global tracing.

### `agrag.observability.record_stage_failure` \{#agrag-observability-record_stage_failure}

```python
record_stage_failure(exc:Exception) -> tuple[str | None, str | None]
```

Record `exc` as an error on the current span, then return its ids.

Call this from inside the `except` block that constructs the
`StageFailure` this exception maps to, and only from code running
under a span `agrag` itself opened (any span this plan or a later one
opens, real or no-op) -- never from a point where the only ambient span
is one a host application opened itself, which this would incorrectly
mark as errored. Every call site this plan adds sits inside at least
one `agrag`-opened root span, so this invariant always holds; a future
caller adding a new StageFailure site outside any `agrag` span would
need its own span first, not a bare call to this function.

The current span must still be open (not yet exited its `with` block)
at the point this runs -- a span that already closed before the
`except` ran is not the current span here, and the ids returned
would correlate to whatever the caller's own ambient span is instead.

**Returns:**

- <code>str | None</code> – The current span's `(trace_id, span_id)` as hex strings, for
- <code>str | None</code> – `StageFailure.trace_id`/`.span_id`, or `(None, None)` when
- <code>tuple\[str | None, str | None\]</code> – `stage_failure_context` would also return that.

### `agrag.observability.record_swallowed_exception` \{#agrag-observability-record_swallowed_exception}

```python
record_swallowed_exception(exc:Exception) -> None
```

Record `exc` on the current span without marking it errored.

For a path that intentionally continues after `exc` without failing
the caller (a best-effort fallback, background recovery): the trace
shows the exception happened, but the span's own status is left alone,
since the caller's behavior did not change because of it. Same
ambient-span invariant as `record_stage_failure` above.

### `agrag.observability.stage_failure_context` \{#agrag-observability-stage_failure_context}

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
