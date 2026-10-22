---
title: agrag.evidence.source_status.source_status
sidebar_label: source_status
---

# `agrag.evidence.source_status.source_status` \{#agrag-evidence-source_status-source_status}

```python
source_status(store:GraphStore, document_key:str, *, vector_store:VectorStore | None = None, dimensions:int | None = None) -> SourceStatus
```

Return committed version, job and index state for one document key.

An expired incomplete job is reported as failed. An active job is reported
as pending, while deleted and unknown keys remain distinct.

**Parameters:**

- **store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – The graph store to read.
- **document_key** (<code>str</code>) – Stable key of the source.
- **vector_store** (<code>[VectorStore](../../vectordb/base/VectorStore.md) | None</code>) – External vector store, or None for graph-native indexes.
- **dimensions** (<code>int | None</code>) – Expected embedding dimension when checking an external store.

**Returns:**

- <code>[SourceStatus](../../common/data_models/evidence/SourceStatus.md)</code> – Source state with the current activation, job lease and index status.
