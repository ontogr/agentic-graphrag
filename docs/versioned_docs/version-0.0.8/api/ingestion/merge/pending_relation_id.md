---
title: agrag.ingestion.merge.pending_relation_id
sidebar_label: pending_relation_id
---

# `agrag.ingestion.merge.pending_relation_id` \{#agrag-ingestion-merge-pending_relation_id}

```python
pending_relation_id(job_id:UUID, canonical_id:UUID) -> UUID
```

Return the id a Cutover Job gives a relation it creates.

Two jobs that create the same relation must not address one row. The job
writes the relation under this id, and the commit folds it into the
canonical id.

**Parameters:**

- **job_id** (<code>UUID</code>) – The in-flight job's id.
- **canonical_id** (<code>UUID</code>) – The id `relation_id` gives the same triple.

**Returns:**

- <code>UUID</code> – The job-scoped relation id.
