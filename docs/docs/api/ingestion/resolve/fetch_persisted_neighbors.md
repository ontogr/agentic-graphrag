---
title: agrag.ingestion.resolve.fetch_persisted_neighbors
sidebar_label: fetch_persisted_neighbors
---

# `agrag.ingestion.resolve.fetch_persisted_neighbors` \{#agrag-ingestion-resolve-fetch_persisted_neighbors}

```python
fetch_persisted_neighbors(entity_ids:Sequence[UUID], *, graph_store:GraphStore, exclude_relation_types:Sequence[str], max_neighbors:int = MAX_NEIGHBORS_PER_ENTITY) -> dict[UUID, list[str]]
```

Fetch a bounded neighbor-relationship sample for persisted entities.

**Parameters:**

- **entity_ids** (<code>Sequence\[UUID\]</code>) – Persisted entity ids to fetch neighbors for.
- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Store to read from.
- **exclude_relation_types** (<code>Sequence\[str\]</code>) – Relation types to omit, such as resolution's
  own system relation types (`MATCHES`, `RESOLVED_AS`, etc.) —
  passed by the caller rather than imported here, since importing
  `SYSTEM_RELATION_TYPES` from `agrag.ingestion.resolve.resolution`
  into this module would create an import cycle (that module already
  imports from this one).
- **max_neighbors** (<code>int</code>) – Maximum neighbor strings kept per entity id.

**Returns:**

- <code>dict\[UUID, list\[str\]\]</code> – Entity id to a list of `"{rel_type} {neighbor_name}"` strings. An
- <code>dict\[UUID, list\[str\]\]</code> – id with no matching relations, and a malformed row, contribute
- <code>dict\[UUID, list\[str\]\]</code> – nothing, so that id is simply absent from the map — every caller
- <code>dict\[UUID, list\[str\]\]</code> – reads through `.get(id, [])`.
