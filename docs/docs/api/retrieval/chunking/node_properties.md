---
title: agrag.retrieval.chunking.node_properties
sidebar_label: node_properties
---

# `agrag.retrieval.chunking.node_properties` \{#agrag-retrieval-chunking-node_properties}

```python
node_properties(node:Any) -> dict[str, Any]
```

Return the properties of a graph node as a plain dict.

Accepts a flat dict, a dict whose values sit under `properties`, and a
neo4j node. Any other value gives an empty dict, which fails Chunk
validation with the missing fields named.

**Parameters:**

- **node** (<code>Any</code>) – The node value from a graph row.

**Returns:**

- <code>dict\[str, Any\]</code> – A new dict of the node properties.
