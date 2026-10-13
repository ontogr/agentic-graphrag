---
title: agrag.common.data_models.graph_record.PENDING_JOB_ID_PROPERTY
sidebar_label: PENDING_JOB_ID_PROPERTY
---

# `agrag.common.data_models.graph_record.PENDING_JOB_ID_PROPERTY` \{#agrag-common-data_models-graph_record-PENDING_JOB_ID_PROPERTY}

```python
PENDING_JOB_ID_PROPERTY = '_pending_job_id'
```

Graph property marking a node or edge as created by an in-flight job.

Written by `GraphStore` on every node or edge a Cutover Job creates. A job
never tags a committed row, so committed data never carries it. Retrieval
query builders exclude rows carrying it, the commit step removes it
atomically, and rollback deletes every row carrying it. Vector-store payloads
hold the job id under the same key.
