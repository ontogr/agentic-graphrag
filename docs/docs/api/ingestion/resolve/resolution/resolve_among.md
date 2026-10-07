---
title: agrag.ingestion.resolve.resolution.resolve_among
sidebar_label: resolve_among
---

# `agrag.ingestion.resolve.resolution.resolve_among` \{#agrag-ingestion-resolve-resolution-resolve_among}

```python
resolve_among(entities:list[Entity], *, embedder:Embedder, tracer:Tracer | None, max_llm_pairs:int) -> ResolutionResult
```

Resolve a fixed set of persisted entities by comparing same-label pairs.

**Parameters:**

- **entities** (<code>list\[[Entity](../../../common/data_models/entity/Entity-ref.md)\]</code>) – The persisted entities to compare. Nothing outside this
  set is read or compared.
- **embedder** (<code>[Embedder](../../../embedding/base/Embedder.md)</code>) – Embeds entity names for fuzzy review.
- **tracer** (<code>Tracer | None</code>) – Traces the resolver.
- **max_llm_pairs** (<code>int</code>) – The most ambiguous pairs per label sent to the LLM.

**Returns:**

- <code>[ResolutionResult](../resolver/ResolutionResult.md)</code> – The resolver result, indexed like `entities`.
