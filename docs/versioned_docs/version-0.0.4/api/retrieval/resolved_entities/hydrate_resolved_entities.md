---
title: agrag.retrieval.resolved_entities.hydrate_resolved_entities
sidebar_label: hydrate_resolved_entities
---

# `agrag.retrieval.resolved_entities.hydrate_resolved_entities` \{#agrag-retrieval-resolved_entities-hydrate_resolved_entities}

```python
hydrate_resolved_entities(graph_store:GraphStore, ids:list[UUID], *, tracer:Tracer | None = None) -> dict[UUID, ResolvedEntity]
```

Hydrate resolved entities by vector-hit identifiers.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where the resolved entities live.
- **ids** (<code>list\[UUID\]</code>) – The vector-hit ids to hydrate.
- **tracer** (<code>Tracer | None</code>) – Opens the hydration span. None opens no recorded span.

**Returns:**

- <code>dict\[UUID, [ResolvedEntity](../../common/data_models/resolved_entity/ResolvedEntity.md)\]</code> – The hydrated resolved entities by id; an empty dict when `ids` is
- <code>dict\[UUID, [ResolvedEntity](../../common/data_models/resolved_entity/ResolvedEntity.md)\]</code> – empty or nothing parsed.
