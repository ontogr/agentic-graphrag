---
title: agrag.common.data_models.vector_record.PENDING_VECTOR_FLAG
sidebar_label: PENDING_VECTOR_FLAG
---

# `agrag.common.data_models.vector_record.PENDING_VECTOR_FLAG` \{#agrag-common-data_models-vector_record-PENDING_VECTOR_FLAG}

```python
PENDING_VECTOR_FLAG = '_pending'
```

Payload flag marking a vector as written by an in-flight Cutover Job.

Mirrored at write time and cleared at commit. Payload filters only match
on present values, so pending-exclusion needs this explicit boolean
rather than relying on the job-id key's absence.

Every backend's filter compiler reads the flag two ways: a filter that
omits it, or sets it `False`, excludes records flagged true while
still returning records written before the flag existed, and a filter
that sets it `True` returns only the flagged records, which is the
maintenance path that has to see a job's own in-flight vectors.
