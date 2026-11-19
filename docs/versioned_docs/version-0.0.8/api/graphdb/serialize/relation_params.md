---
title: agrag.graphdb.serialize.relation_params
sidebar_label: relation_params
---

# `agrag.graphdb.serialize.relation_params` \{#agrag-graphdb-serialize-relation_params}

```python
relation_params(record:RelationRecord, *, pending_job_id:UUID | None = None) -> dict[str, Any]
```

Build the `$records` entry for a relationship upsert.

The Cutover Job tag travels in its own key for the same reason as in
`node_params`: only an edge the job creates carries it.

**Parameters:**

- **record** (<code>[RelationRecord](../../common/data_models/graph_record/RelationRecord.md)</code>) – The relation record to serialize.
- **pending_job_id** (<code>UUID | None</code>) – The in-flight job's id, or None outside a job.

**Returns:**

- <code>dict\[str, Any\]</code> – A dict with `id`, `start_id`, `end_id`, `properties`
- <code>dict\[str, Any\]</code> – (converted), and `pending_job_id` (the tag as a string, or None).
