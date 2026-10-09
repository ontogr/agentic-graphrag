---
title: agrag.graphdb.serialize.relation_params
sidebar_label: relation_params
---

# `agrag.graphdb.serialize.relation_params` \{#agrag-graphdb-serialize-relation_params}

```python
relation_params(record:RelationRecord) -> dict[str, Any]
```

Build the `$records` entry for a relationship upsert.

The Cutover Job tag is split out of `properties` for the same reason
as in :func:`node_params`: only an edge the job creates carries it.

**Parameters:**

- **record** (<code>[RelationRecord](../../common/data_models/graph_record/RelationRecord.md)</code>) – The relation record to serialize.

**Returns:**

- <code>dict\[str, Any\]</code> – A dict with `id`, `start_id`, `end_id`, `properties`
- <code>dict\[str, Any\]</code> – (converted, without the pending tag), and `pending_job_id` (the
- <code>dict\[str, Any\]</code> – tag, or None).
