---
title: agrag.ingestion.community.delete_all_communities
sidebar_label: delete_all_communities
---

# `agrag.ingestion.community.delete_all_communities` \{#agrag-ingestion-community-delete_all_communities}

```python
delete_all_communities(graph_store:GraphStore | GraphStoreTransaction, *, batch_size:int = _DEFAULT_DELETE_BATCH_SIZE) -> None
```

Delete every Community node and its edges, in batches.

Repeats the bounded delete until a batch reports fewer than
batch_size rows deleted.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md) | [GraphStoreTransaction](../../graphdb/base/GraphStoreTransaction.md)</code>) – Where the delete runs. Accepts either a
  `GraphStore` or a `GraphStoreTransaction` handle so a
  caller inside `store.transaction()` can delete and rewrite
  communities atomically.
- **batch_size** (<code>int</code>) – Community nodes deleted per statement.
