---
title: agrag.common.graph_rows.node_properties
sidebar_label: node_properties
---

# `agrag.common.graph_rows.node_properties` \{#agrag-common-graph_rows-node_properties}

```python
node_properties(node:Any) -> dict[str, Any]
```

Return the properties of a graph node as a new dict.

Accepts a flat dict, a dict that holds its values under `properties`, and
a neo4j node or other value that `dict()` can read. The nested
`properties` values win over top-level keys of the same name.

**Parameters:**

- **node** (<code>Any</code>) – The node value from a graph row.

**Returns:**

- <code>dict\[str, Any\]</code> – A new dict of the node properties. A value that `dict()` cannot read
- <code>dict\[str, Any\]</code> – gives an empty dict, so the caller's validation names the missing
- <code>dict\[str, Any\]</code> – fields.
