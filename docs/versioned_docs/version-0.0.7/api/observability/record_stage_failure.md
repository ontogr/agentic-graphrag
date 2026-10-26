---
title: agrag.observability.record_stage_failure
sidebar_label: record_stage_failure
---

# `agrag.observability.record_stage_failure` \{#agrag-observability-record_stage_failure}

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
