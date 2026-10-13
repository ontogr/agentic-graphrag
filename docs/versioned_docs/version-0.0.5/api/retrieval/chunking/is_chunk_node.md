---
title: agrag.retrieval.chunking.is_chunk_node
sidebar_label: is_chunk_node
---

# `agrag.retrieval.chunking.is_chunk_node` \{#agrag-retrieval-chunking-is_chunk_node}

```python
is_chunk_node(value:object) -> bool
```

Tell whether a node value is a stored Chunk node.

A driver node is judged by its labels. A plain property dict carries no
labels, so it is judged by the fields only a Chunk node holds.

**Parameters:**

- **value** (<code>object</code>) – The node value from a graph row.

**Returns:**

- <code>bool</code> – True when the value is labelled `Chunk`, or is a property dict
- <code>bool</code> – with the chunk-only fields. False for any other value.
