---
title: agrag.graphdb.serialize.node_params
sidebar_label: node_params
---

# `agrag.graphdb.serialize.node_params` \{#agrag-graphdb-serialize-node_params}

```python
node_params(record:NodeRecord) -> dict[str, Any]
```

Build the `$records` entry for a node upsert.

The Cutover Job tag is split out of `properties` into its own key
because the upsert queries apply it with `ON CREATE SET`: a job tags
the nodes it creates, never a node it writes over. Left inside the
applied property map it would be set on existing nodes too, which
would hide a committed node from retrieval for the job's duration and
put it in reach of the job's rollback — and rollback deletes tagged
rows.

**Parameters:**

- **record** (<code>[NodeRecord](../../common/data_models/graph_record/NodeRecord.md)</code>) – The node record to serialize.

**Returns:**

- <code>dict\[str, Any\]</code> – A dict with `id` (string), `properties` (converted, without
- <code>dict\[str, Any\]</code> – the pending tag), and `pending_job_id` (the tag, or None).
