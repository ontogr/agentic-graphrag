---
title: agrag.candidates.patch.candidate_patch
sidebar_label: candidate_patch
---

# `agrag.candidates.patch.candidate_patch` \{#agrag-candidates-patch-candidate_patch}

```python
candidate_patch(graph_store:GraphStore, schema:GraphSchema, *, ids:Sequence[UUID] | None = None, now:datetime | None = None) -> SchemaPatch
```

Build a patch from approved candidate records in the graph.

When `ids` is omitted, all approved candidates are selected. Supplied
ids are loaded, then non-approved records and records with unresolved
endpoints are excluded from the planned patch.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Store containing candidates and endpoint entities.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – Current schema used to plan additions.
- **ids** (<code>Sequence\[UUID\] | None</code>) – Candidate ids to consider, or all approved ids when omitted.
- **now** (<code>datetime | None</code>) – Patch creation time, or the current UTC time when omitted.

**Returns:**

- <code>[SchemaPatch](../../common/data_models/candidate_review/SchemaPatch.md)</code> – Deterministic patch based on the selected approved records.
