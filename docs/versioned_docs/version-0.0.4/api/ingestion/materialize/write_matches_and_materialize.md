---
title: agrag.ingestion.materialize.write_matches_and_materialize
sidebar_label: write_matches_and_materialize
---

# `agrag.ingestion.materialize.write_matches_and_materialize` \{#agrag-ingestion-materialize-write_matches_and_materialize}

```python
write_matches_and_materialize(decisions:list[MatchDecision], *, graph_store:GraphStore, schema:GraphSchema, members:list[Entity], pending_job_id:str | None = None, tracer:Tracer | None = None) -> MaterializationResult
```

Persist matches and materialize their supplied connected component.

Callers fetch the bounded affected component before invoking this function.
The resolved node is always recomputed from that current membership.

**Parameters:**

- **decisions** (<code>list\[[MatchDecision](MatchDecision.md)\]</code>) – The confirmed matches to persist.
- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where matches and materializations are written.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – The schema the members belong to.
- **members** (<code>list\[[Entity](../../common/data_models/entity/Entity-ref.md)\]</code>) – The component members the resolved node is computed from.
- **pending_job_id** (<code>str | None</code>) – The in-flight Cutover Job's id, tagging the match
  edges and materialized nodes until that job commits. None
  writes untagged, for callers outside a job.
- **tracer** (<code>Tracer | None</code>) – Passed to description summarization.

**Raises:**

- <code>ValueError</code> – No decisions are supplied, or a decision references a
  member outside the supplied component.
