---
title: agrag.observability.record_swallowed_exception
sidebar_label: record_swallowed_exception
---

# `agrag.observability.record_swallowed_exception` \{#agrag-observability-record_swallowed_exception}

```python
record_swallowed_exception(exc:Exception) -> None
```

Record `exc` on the current span without marking it errored.

For a path that intentionally continues after `exc` without failing
the caller (a best-effort fallback, background recovery): the trace
shows the exception happened, but the span's own status is left alone,
since the caller's behavior did not change because of it. Same
ambient-span invariant as `record_stage_failure` above.
