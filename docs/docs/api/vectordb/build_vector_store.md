---
title: agrag.vectordb.build_vector_store
sidebar_label: build_vector_store
---

# `agrag.vectordb.build_vector_store` \{#agrag-vectordb-build_vector_store}

```python
build_vector_store(value:VectorStoreName | VectorStore, *, tracer:Tracer | None = None) -> VectorStore
```

Construct a named vector index or return an existing instance unchanged.

**Parameters:**

- **value** (<code>[VectorStoreName](VectorStoreName.md) | [VectorStore](base/VectorStore.md)</code>) – A supported backend name or an existing vector store.
- **tracer** (<code>Tracer | None</code>) – Forwarded to a newly constructed store. An existing instance's
  tracer is fixed at its own construction.

**Returns:**

- <code>[VectorStore](base/VectorStore.md)</code> – A vector store that initializes on first use.

**Raises:**

- <code>ValueError</code> – The name is unknown, or tracer accompanies an instance.
