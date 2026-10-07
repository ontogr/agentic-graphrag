---
title: agrag.vectordb.build_vector_store
sidebar_label: build_vector_store
---

# `agrag.vectordb.build_vector_store` \{#agrag-vectordb-build_vector_store}

```python
build_vector_store(value:VectorStoreName | VectorStore, *, tracer:Tracer | None = None) -> VectorStore
```

Build a vector store from a backend name, or return one unchanged.

**Parameters:**

- **value** (<code>VectorStoreName | [VectorStore](base/VectorStore.md)</code>) – `"qdrant"` or `"weaviate"`, or an already-constructed
  `VectorStore` for full control over settings.
- **tracer** (<code>Tracer | None</code>) – Passed to the newly-built store. Not valid together with an
  already-constructed `value` -- that instance's tracer, if any,
  was already fixed at its own construction.

**Returns:**

- <code>[VectorStore](base/VectorStore.md)</code> – A ready-to-use vector store.

**Raises:**

- <code>ValueError</code> – `tracer` is given together with an already-constructed
  `value`.
