---
title: agrag.ingestion.resolved_entities.rebuild_resolved_entities
sidebar_label: rebuild_resolved_entities
---

# `agrag.ingestion.resolved_entities.rebuild_resolved_entities` \{#agrag-ingestion-resolved_entities-rebuild_resolved_entities}

```python
rebuild_resolved_entities(seed_ids:list[UUID], *, graph_store:GraphStore, schema:GraphSchema, tracer:Tracer | None = None) -> list[RebuildResult]
```

Rebuild the resolved entity of each committed component from its seeds.

The matches already exist, so no match decision is written or changed.
The resolved nodes and their `RESOLVED_AS` memberships are rebuilt,
each membership carrying the newest committed match time when one
exists. Each component is read as it stands now, replacing whatever
resolved entities its members belonged to. A seed whose entity is
gone, or whose component has fewer than two members, is skipped:
nothing is left to rebuild for it. Safe to run again on the same
seeds.

**Parameters:**

- **seed_ids** (<code>list\[UUID\]</code>) – One member id per component to rebuild. Seeds that share a
  component rebuild it once.
- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where the components are read and rewritten.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – The schema the members belong to.
- **tracer** (<code>Tracer | None</code>) – Passed to description summarization.

**Returns:**

- <code>list\[[RebuildResult](RebuildResult.md)\]</code> – One result per rebuilt component, in seed order.
