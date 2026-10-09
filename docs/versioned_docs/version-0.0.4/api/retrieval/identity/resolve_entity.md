---
title: agrag.retrieval.identity.resolve_entity
sidebar_label: resolve_entity
---

# `agrag.retrieval.identity.resolve_entity` \{#agrag-retrieval-identity-resolve_entity}

```python
resolve_entity(graph_store:GraphStore, entity_id:UUID, *, tracer:Tracer | None = None) -> Entity
```

Return the live Entity behind an id, following merged_into.

Every retrieval path that can produce an entity id must call
this before wrapping the id in a SearchResult. This is the
single place the merged_into invariant is enforced.

A merge writes a `merged_into` property on the tombstone rather
than a relationship, so the chain is walked one hop per query.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where the entity and its possible tombstone
  chain live.
- **entity_id** (<code>UUID</code>) – The id a retrieval method found, which may or
  may not still be live.
- **tracer** (<code>Tracer | None</code>) – Opens the resolution span. None opens no recorded span.

**Returns:**

- <code>[Entity](../../common/data_models/entity/Entity-ref.md)</code> – The live Entity, after resolving zero or more hops.

**Raises:**

- <code>ValueError</code> – The id does not exist, its node cannot be parsed,
  the chain points at a missing node, the chain cycles, or it
  is longer than `MAX_MERGE_HOPS`.
