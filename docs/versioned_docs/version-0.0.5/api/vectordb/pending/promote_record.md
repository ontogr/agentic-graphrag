---
title: agrag.vectordb.pending.promote_record
sidebar_label: promote_record
---

# `agrag.vectordb.pending.promote_record` \{#agrag-vectordb-pending-promote_record}

```python
promote_record(record:VectorRecord) -> VectorRecord
```

Return the committed record a staged record stands for.

**Parameters:**

- **record** (<code>[VectorRecord](../../common/data_models/vector_record/VectorRecord.md)</code>) – A record read back from the store with a staging id.

**Returns:**

- <code>[VectorRecord](../../common/data_models/vector_record/VectorRecord.md)</code> – A record under the real id, without the pending keys.

**Raises:**

- <code>KeyError</code> – The record carries no real id, so it is not staged.
