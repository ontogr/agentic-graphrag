---
title: agrag.ingestion.community.detect_communities
sidebar_label: detect_communities
---

# `agrag.ingestion.community.detect_communities` \{#agrag-ingestion-community-detect_communities}

```python
detect_communities(graph_store:GraphStore, *, embedder:Embedder, tracer:Tracer | None = None, apply:bool = False, max_cluster_size:int = 10, resolution:float = 1.0, seed:int | None = 3735928559) -> CommunityDetectionReport
```

Detect entity communities via hierarchical Leiden.

Reads every live domain relation across the whole graph, not only one
entity label, because community structure spans entity types. It builds a
weighted edge list and runs hierarchical Leiden off the event loop. With
`apply=True` the run is a full recompute: it deletes every earlier
Community node and MEMBER_OF edge before it stores the new ones.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where relations and entities are read and communities are
  written.
- **embedder** (<code>[Embedder](../../embedding/base/Embedder.md)</code>) – Embeds the community summaries.
- **tracer** (<code>Tracer | None</code>) – Opens the detection span. None opens no recorded span.
- **apply** (<code>bool</code>) – Write the communities. False returns a report only.
- **max_cluster_size** (<code>int</code>) – Forwarded to `compute_communities`.
- **resolution** (<code>float</code>) – Forwarded to `compute_communities`.
- **seed** (<code>int | None</code>) – Forwarded to `compute_communities`.

**Returns:**

- <code>[CommunityDetectionReport](../reports/community_detection_report/CommunityDetectionReport.md)</code> – A report of every community found, applied or not. A community report
- <code>[CommunityDetectionReport](../reports/community_detection_report/CommunityDetectionReport.md)</code> – failure appears in `failures`.

**Raises:**

- <code>[CommunityDetectionMissingExtraError](CommunityDetectionMissingExtraError.md)</code> – graspologic-native is not
  installed.
