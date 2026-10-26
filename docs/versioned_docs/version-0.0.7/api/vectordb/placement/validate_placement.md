---
title: agrag.vectordb.placement.validate_placement
sidebar_label: validate_placement
---

# `agrag.vectordb.placement.validate_placement` \{#agrag-vectordb-placement-validate_placement}

```python
validate_placement(graph_store:GraphStore, *, vector_store:VectorStore | None, dimensions:int, distance:Distance, write:bool, check_embedding:bool = True) -> None
```

Compare placement, creating it on first open only when write is true.

The store and collection prefix always have to match. Dimensions and
distance describe the embedding, so they are compared only when
`check_embedding` is true. A reader that checks the embedding on each
search can leave that check to the search.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – The graph that holds the placement record.
- **vector_store** (<code>[VectorStore](../base/VectorStore.md) | None</code>) – The external store in use, or None for graph-native
  indexes.
- **dimensions** (<code>int</code>) – The dimensions of the embedding in use.
- **distance** (<code>[Distance](../../common/data_models/vector_record/Distance.md)</code>) – The distance metric of the embedding in use.
- **write** (<code>bool</code>) – Whether to record the placement when the graph has none.
- **check_embedding** (<code>bool</code>) – Whether to compare dimensions and distance.

**Raises:**

- <code>[VectorPlacementError](../errors/VectorPlacementError.md)</code> – Store, prefix, dimensions or distance differ.
