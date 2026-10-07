---
title: agrag.ingestion.merge.apply_merge
sidebar_label: apply_merge
---

# `agrag.ingestion.merge.apply_merge` \{#agrag-ingestion-merge-apply_merge}

```python
apply_merge(plan:MergePlan, *, graph_store:GraphStore, schema:GraphSchema, pending_job_id:str | None = None) -> None
```

Write a computed MergePlan to storage.

Every call runs inside one GraphStore transaction: it upserts the
survivor and records a merge-key alias for its current name. A
failure partway through leaves no half-written state: no survivor
without its alias.

**Parameters:**

- **plan** (<code>[MergePlan](MergePlan.md)</code>) – The merge to write.
- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where the merge is written.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – The schema the survivor's label belongs to.
- **pending_job_id** (<code>str | None</code>) – The in-flight Cutover Job's id, tagging the
  survivor node and its aliases until that job commits. None
  writes untagged, for callers outside a job.

**Raises:**

- <code>GraphStoreAliasConflictError</code> – An accepted merge_key is already owned
  by a live entity outside this merge's own survivor id -- a
  concurrent writer accepted that name as an alias of, or
  created it as the canonical name of, a different entity.
