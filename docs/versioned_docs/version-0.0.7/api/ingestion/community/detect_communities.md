---
title: agrag.ingestion.community.detect_communities
sidebar_label: detect_communities
---

# `agrag.ingestion.community.detect_communities` \{#agrag-ingestion-community-detect_communities}

```python
detect_communities(graph_store:GraphStore, *, schema:GraphSchema, embedder:Embedder, tracer:Tracer | None = None, apply:bool = False, vector_sync:VectorSync | None = None, max_cluster_size:int = 10, resolution:float = 1.0, seed:int | None = 3735928559) -> CommunityDetectionReport
```

Detect entity communities via hierarchical Leiden.

Reads relationships declared by the active schema between nodes carrying
declared entity labels. Stored relationships outside the schema do not
affect clustering. It builds a weighted edge list and runs hierarchical
Leiden off the event loop. With `apply=True` the run is a full recompute:
it deletes every earlier Community node and MEMBER_OF edge before it stores
the new ones.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where relations and entities are read and communities are
  written.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – The active entity and relation types for this graph.
- **embedder** (<code>[Embedder](../../embedding/base/Embedder.md)</code>) – Embeds the community summaries.
- **tracer** (<code>Tracer | None</code>) – Opens the detection span. None opens no recorded span.
- **apply** (<code>bool</code>) – Write the communities. False returns a report only.
- **vector_sync** (<code>[VectorSync](../vector_sync/VectorSync.md) | None</code>) – Mirrors community vectors outside the graph when set.
- **max_cluster_size** (<code>int</code>) – Forwarded to `compute_communities`.
- **resolution** (<code>float</code>) – Forwarded to `compute_communities`.
- **seed** (<code>int | None</code>) – Forwarded to `compute_communities`.

**Returns:**

- <code>[CommunityDetectionReport](../reports/community_detection_report/CommunityDetectionReport.md)</code> – A report of every community found, applied or not. A community report
- <code>[CommunityDetectionReport](../reports/community_detection_report/CommunityDetectionReport.md)</code> – failure appears in `failures`.

**Raises:**

- <code>[CommunityDetectionMissingExtraError](CommunityDetectionMissingExtraError.md)</code> – graspologic-native is not
  installed.
