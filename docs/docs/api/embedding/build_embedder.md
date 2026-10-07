---
title: agrag.embedding.build_embedder
sidebar_label: build_embedder
---

# `agrag.embedding.build_embedder` \{#agrag-embedding-build_embedder}

```python
build_embedder(value:str | Embedder, *, tracer:Tracer | None = None) -> Embedder
```

Build an embedder from a model name, or return an embedder unchanged.

**Parameters:**

- **value** (<code>str | [Embedder](base/Embedder.md)</code>) – A FastEmbed model name, such as
  `"ibm-granite/granite-embedding-small-english-r2"` (the default
  model), or an already-constructed `Embedder` for full control
  over batching or caching. To use a sentence-transformers model,
  pass a `SentenceTransformerEmbedder`, which needs the
  `embed-local` extra.
- **tracer** (<code>Tracer | None</code>) – Passed to the newly-built embedder. Not valid together with
  an already-constructed `value`. That instance's tracer, if
  any, was already fixed at its own construction.

**Returns:**

- <code>[Embedder](base/Embedder.md)</code> – A ready-to-use embedder.

**Raises:**

- <code>ValueError</code> – `tracer` is given together with an already-constructed
  `value`.
