---
title: agrag.common.data_models.graph_record.tag_pending
sidebar_label: tag_pending
---

# `agrag.common.data_models.graph_record.tag_pending` \{#agrag-common-data_models-graph_record-tag_pending}

```python
tag_pending(record:_RecordT, job_id:UUID | str | None) -> _RecordT
```

Stamp a write record with the Cutover Job that is writing it.

The tag reaches the graph only when the write creates its row; the
upsert queries apply it with `ON CREATE SET`.

No-op outside a job, so pipeline stages thread their optional job id
through this unconditionally instead of branching at every write.

**Parameters:**

- **record** (<code>\_RecordT</code>) – The node or relationship record about to be written.
- **job_id** (<code>UUID | str | None</code>) – The in-flight job's id, or None outside a job.

**Returns:**

- <code>\_RecordT</code> – A tagged copy when a job id was given; otherwise the original record.
