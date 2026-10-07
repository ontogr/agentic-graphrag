---
title: agrag.ingestion.merge.resolve_description
sidebar_label: resolve_description
---

# `agrag.ingestion.merge.resolve_description` \{#agrag-ingestion-merge-resolve_description}

```python
resolve_description(candidates:list[object], *, settings:Any | None = None, client:Any | None = None, tracer:Tracer | None = None) -> tuple[object, bool, Any | None]
```

Resolve a description field, trying LLM summarization.

A single distinct candidate needs no LLM call. Multiple candidates try
LLM summarization; on failure, fall back to concatenation.

**Parameters:**

- **candidates** (<code>list\[object\]</code>) – Candidate values in encounter order.
- **settings** (<code>Any | None</code>) – LLM settings for summarization. None uses defaults.
- **client** (<code>Any | None</code>) – An already-built BAML client for tests.
- **tracer** (<code>Tracer | None</code>) – Opens the `agrag.merge.resolve_description` span and the
  LLM call spans below it.

**Returns:**

- <code>tuple\[object, bool, Any | None\]</code> – The resolved value, whether it conflicted, and an optional failure.
