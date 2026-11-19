---
title: agrag.graphdb.entities.load_entities
sidebar_label: load_entities
---

# `agrag.graphdb.entities.load_entities` \{#agrag-graphdb-entities-load_entities}

```python
load_entities(graph_store:GraphStore, ids:Sequence[UUID], *, tracer:Tracer | None = None) -> dict[UUID, Entity]
```

Load the committed entities stored under the given ids.

Reads in batches of `LOAD_BATCH_SIZE`. Entities that an in-flight
Cutover Job wrote are not returned.

**Parameters:**

- **graph_store** (<code>[GraphStore](../base/GraphStore.md)</code>) – Where the entities live.
- **ids** (<code>Sequence\[UUID\]</code>) – The entity ids to load. Duplicates are read once.
- **tracer** (<code>Tracer | None</code>) – Opens the loading span. None opens no recorded span.

**Returns:**

- <code>dict\[UUID, [Entity](../../common/data_models/entity/Entity-ref.md)\]</code> – The entities by id. An id with no committed entity is absent from the
- <code>dict\[UUID, [Entity](../../common/data_models/entity/Entity-ref.md)\]</code> – result, so the caller decides whether that is an error.

**Raises:**

- <code>ValueError</code> – A stored node under a requested id cannot be parsed into
  an entity.
- <code>Exception</code> – Whatever `graph_store` raised while reading.
