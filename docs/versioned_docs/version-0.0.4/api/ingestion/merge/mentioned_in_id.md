---
title: agrag.ingestion.merge.mentioned_in_id
sidebar_label: mentioned_in_id
---

# `agrag.ingestion.merge.mentioned_in_id` \{#agrag-ingestion-merge-mentioned_in_id}

```python
mentioned_in_id(chunk_id:UUID, entity_id:UUID) -> UUID
```

Return the deterministic id for a new Chunk -[:MENTIONED_IN]-> Entity edge.

Only a fresh id for a pair with no persisted edge yet is guaranteed to equal
this. A caller writing to an already-persisted pair should look up the
edge by its endpoints first and fall back to this id only when none is
found.

**Parameters:**

- **chunk_id** (<code>UUID</code>) – The Chunk's id.
- **entity_id** (<code>UUID</code>) – The Entity's id.

**Returns:**

- <code>UUID</code> – The edge id. Deterministic: same pair always returns same id.
