---
title: agrag.ingestion.resolved_entities.write_matches_and_rebuild
sidebar_label: write_matches_and_rebuild
---

# `agrag.ingestion.resolved_entities.write_matches_and_rebuild` \{#agrag-ingestion-resolved_entities-write_matches_and_rebuild}

```python
write_matches_and_rebuild(decisions:list[MatchDecision], *, graph_store:GraphStore, schema:GraphSchema, members:list[Entity], pending_job_id:str | None = None, deferred:DeferredWrites | None = None, tracer:Tracer | None = None, vector_sync:VectorSync | None = None) -> RebuildResult
```

Persist matches and rebuild their supplied connected component.

Callers fetch the bounded affected component before invoking this function.
The resolved node is always recomputed from that current membership.

**Parameters:**

- **decisions** (<code>list\[[MatchDecision](MatchDecision.md)\]</code>) – The confirmed matches to persist.
- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where matches and resolved entities are written.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – The schema the members belong to.
- **members** (<code>list\[[Entity](../../common/data_models/entity/Entity-ref.md)\]</code>) – The component members the resolved node is computed from.
- **pending_job_id** (<code>str | None</code>) – The in-flight Cutover Job's id, tagging the match
  edges and resolved entity nodes until that job commits. None
  writes untagged, for callers outside a job.
- **deferred** (<code>[DeferredWrites](../../common/data_models/graph_record/DeferredWrites.md) | None</code>) – Receives the writes over committed rows, such as a match
  edge that already exists. Required when `pending_job_id` is set.
- **tracer** (<code>Tracer | None</code>) – Passed to description summarization.
- **vector_sync** (<code>[VectorSync](../vector_sync/VectorSync.md) | None</code>) – Removes stale resolved-entity vectors when set.

**Raises:**

- <code>ValueError</code> – No decisions are supplied, a decision references a
  member outside the supplied component, or `pending_job_id` is
  set and `deferred` is None.
