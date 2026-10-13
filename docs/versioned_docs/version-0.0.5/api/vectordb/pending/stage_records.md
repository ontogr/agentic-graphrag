---
title: agrag.vectordb.pending.stage_records
sidebar_label: stage_records
---

# `agrag.vectordb.pending.stage_records` \{#agrag-vectordb-pending-stage_records}

```python
stage_records(records:Sequence[VectorRecord], pending_job_id:UUID | None) -> list[VectorRecord]
```

Return records ready to write for one job, or unchanged outside a job.

**Parameters:**

- **records** (<code>Sequence\[[VectorRecord](../../common/data_models/vector_record/VectorRecord.md)\]</code>) – The records the caller wants to write.
- **pending_job_id** (<code>UUID | None</code>) – The in-flight job's id. None writes the records as
  committed.

**Returns:**

- <code>list\[[VectorRecord](../../common/data_models/vector_record/VectorRecord.md)\]</code> – With a job id, copies under staging ids that carry the pending flag,
- <code>list\[[VectorRecord](../../common/data_models/vector_record/VectorRecord.md)\]</code> – the job id and the real id. Without one, the records unchanged.

**Raises:**

- <code>ValueError</code> – A record payload uses a reserved pending key.
