---
title: agrag.retrieval.chunking.parse_chunk_node
sidebar_label: parse_chunk_node
---

# `agrag.retrieval.chunking.parse_chunk_node` \{#agrag-retrieval-chunking-parse_chunk_node}

```python
parse_chunk_node(value:object) -> Chunk | None
```

Build a Chunk from a node value, or return None when it is not a chunk.

**Parameters:**

- **value** (<code>object</code>) – The node value from a graph row.

**Returns:**

- <code>[Chunk](../../common/data_models/chunk/Chunk-ref.md) | None</code> – The parsed Chunk, or None when the value fails Chunk validation.
