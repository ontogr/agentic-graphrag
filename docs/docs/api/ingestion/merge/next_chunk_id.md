---
title: agrag.ingestion.merge.next_chunk_id
sidebar_label: next_chunk_id
---

# `agrag.ingestion.merge.next_chunk_id` \{#agrag-ingestion-merge-next_chunk_id}

```python
next_chunk_id(from_chunk_id:UUID, to_chunk_id:UUID) -> UUID
```

Return the deterministic id for a Chunk -[:NEXT_CHUNK]-> Chunk edge.

**Parameters:**

- **from_chunk_id** (<code>UUID</code>) – The id of the earlier chunk in sequence.
- **to_chunk_id** (<code>UUID</code>) – The id of the chunk that follows it.

**Returns:**

- <code>UUID</code> – The edge id. Same pair always returns the same id.
