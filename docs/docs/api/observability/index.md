---
title: agrag.observability
sidebar_position: 10
---


# `agrag.observability` \{#agrag-observability}

OpenTelemetry wiring for the ingestion layer.

This module imports only `opentelemetry-api`. The SDK and exporters stay in
the optional `observability` extra and are never imported here; a caller
wires them before opening a graph. The tracer is constructor-injected, never
ambient: `get_tracer(None)` returns an explicit no-op tracer instead of
reaching the global `TracerProvider`.

**Functions:**

- [**get_tracer**](get_tracer.md) – Return a usable tracer.
- [**record_stage_failure**](record_stage_failure.md) – Record `exc` as an error on the current span, then return its ids.
- [**record_swallowed_exception**](record_swallowed_exception.md) – Record `exc` on the current span without marking it errored.
- [**stage_failure_context**](stage_failure_context.md) – Return the current span's trace and span id as hex, or (None, None).

**Attributes:**

- [**DB_COLLECTION_NAME**](DB_COLLECTION_NAME.md) –
- [**DB_NAMESPACE**](DB_NAMESPACE.md) –
- [**DB_OPERATION_BATCH_SIZE**](DB_OPERATION_BATCH_SIZE.md) –
- [**DB_QUERY_PARAMETER_PREFIX**](DB_QUERY_PARAMETER_PREFIX.md) –
- [**DB_QUERY_TEXT**](DB_QUERY_TEXT.md) –
- [**DB_SYSTEM_NAME**](DB_SYSTEM_NAME.md) –
