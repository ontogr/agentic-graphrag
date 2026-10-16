---
title: agrag.graphdb.serialize.node_params
sidebar_label: node_params
---

# `agrag.graphdb.serialize.node_params` \{#agrag-graphdb-serialize-node_params}

```python
node_params(record:NodeRecord, *, pending_job_id:UUID | None = None) -> dict[str, Any]
```

Build the `$records` entry for a node upsert.

The Cutover Job tag travels in its own key, not inside `properties`,
because the upsert queries apply it with `ON CREATE SET`: a job tags
the nodes it creates, never a node it writes over. Left inside the
applied property map it would be set on existing nodes too, which
would hide a committed node from retrieval for the job's duration and
put it in reach of the job's rollback, and rollback deletes tagged
rows.

**Parameters:**

- **record** (<code>[NodeRecord](../../common/data_models/graph_record/NodeRecord.md)</code>) – The node record to serialize.
- **pending_job_id** (<code>UUID | None</code>) – The in-flight job's id, or None outside a job.

**Returns:**

- <code>dict\[str, Any\]</code> – A dict with `id` (string), `properties` (converted), and
- <code>dict\[str, Any\]</code> – `pending_job_id` (the tag as a string, or None).
