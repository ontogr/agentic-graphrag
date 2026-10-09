---
title: agrag.retrieval.tracing.record_chunks
sidebar_label: record_chunks
---

# `agrag.retrieval.tracing.record_chunks` \{#agrag-retrieval-tracing-record_chunks}

```python
record_chunks(span:Span, chunks:Sequence[Chunk]) -> None
```

Record hydrated chunks as OpenTelemetry-safe attributes.

**Parameters:**

- **span** (<code>Span</code>) – The active retrieval span.
- **chunks** (<code>Sequence\[[Chunk](../../common/data_models/chunk/Chunk-ref.md)\]</code>) – Parent chunks attached to child results.

**Returns:**

- <code>None</code> – None.
