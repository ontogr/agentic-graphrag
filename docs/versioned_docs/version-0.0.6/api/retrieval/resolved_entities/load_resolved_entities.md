---
title: agrag.retrieval.resolved_entities.load_resolved_entities
sidebar_label: load_resolved_entities
---

# `agrag.retrieval.resolved_entities.load_resolved_entities` \{#agrag-retrieval-resolved_entities-load_resolved_entities}

```python
load_resolved_entities(graph_store:GraphStore, ids:list[UUID], *, tracer:Tracer | None = None) -> dict[UUID, ResolvedEntity]
```

Load resolved entities by vector-hit identifiers.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where the resolved entities live.
- **ids** (<code>list\[UUID\]</code>) – The vector-hit ids to load.
- **tracer** (<code>Tracer | None</code>) – Opens the loading span. None opens no recorded span.

**Returns:**

- <code>dict\[UUID, [ResolvedEntity](../../common/data_models/resolved_entity/ResolvedEntity.md)\]</code> – The loaded resolved entities by id; an empty dict when `ids` is
- <code>dict\[UUID, [ResolvedEntity](../../common/data_models/resolved_entity/ResolvedEntity.md)\]</code> – empty or nothing parsed.
