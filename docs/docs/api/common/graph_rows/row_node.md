---
title: agrag.common.graph_rows.row_node
sidebar_label: row_node
---

# `agrag.common.graph_rows.row_node` \{#agrag-common-graph_rows-row_node}

```python
row_node(row:Any) -> Any
```

Return the node a result row holds under `n`, or the row itself.

**Parameters:**

- **row** (<code>Any</code>) – One row of a read. Queries that return a node name it `n`.
  A row that is already the node is returned unchanged.

**Returns:**

- <code>Any</code> – The node value.
