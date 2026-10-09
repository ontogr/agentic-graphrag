---
title: agrag.retrieval.chunking.parse_chunk_node
sidebar_label: parse_chunk_node
---

# `agrag.retrieval.chunking.parse_chunk_node` \{#agrag-retrieval-chunking-parse_chunk_node}

```python
parse_chunk_node(value:object) -> Chunk | None
```

Build a Chunk from a chunk-shaped row value, or None.

Accepts a plain dict, a dict carrying `properties`, or a neo4j
Node-like object. Legacy `content_kind` values map to the current
pair once here, and `section_ids` parses per item, so stored data
is kept whenever its id, document id, and provenance are valid.

**Parameters:**

- **value** (<code>object</code>) – The chunk node value from a graph row.

**Returns:**

- <code>[Chunk](../../common/data_models/chunk/Chunk-ref.md) | None</code> – The parsed Chunk, or None when the value lacks an id, a document id,
  or valid provenance, or is a table or figure node.
