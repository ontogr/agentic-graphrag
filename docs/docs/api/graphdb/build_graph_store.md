---
title: agrag.graphdb.build_graph_store
sidebar_label: build_graph_store
---

# `agrag.graphdb.build_graph_store` \{#agrag-graphdb-build_graph_store}

```python
build_graph_store(value:GraphStoreName | GraphStore, *, tracer:Tracer | None = None) -> GraphStore
```

Build a graph store from a backend name, or return one unchanged.

**Parameters:**

- **value** (<code>[GraphStoreName](GraphStoreName.md) | [GraphStore](base/GraphStore.md)</code>) – `"neo4j"`, or an already-constructed `GraphStore`.
- **tracer** (<code>Tracer | None</code>) – Passed to the newly-built store. Not valid together with an
  already-constructed `value` -- that instance's tracer, if any,
  was already fixed at its own construction.

**Returns:**

- <code>[GraphStore](base/GraphStore.md)</code> – A ready-to-use graph store.

**Raises:**

- <code>ValueError</code> – `tracer` is given together with an already-constructed
  `value`.
