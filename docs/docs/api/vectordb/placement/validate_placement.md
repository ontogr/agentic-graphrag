---
title: agrag.vectordb.placement.validate_placement
sidebar_label: validate_placement
---

# `agrag.vectordb.placement.validate_placement` \{#agrag-vectordb-placement-validate_placement}

```python
validate_placement(graph_store:GraphStore, *, vector_store:VectorStore | None, dimensions:int, distance:Distance, write:bool) -> None
```

Compare placement, creating it on first open only when write is true.

**Raises:**

- <code>[VectorPlacementError](../errors/VectorPlacementError.md)</code> – Store, prefix, dimensions or distance differ.
