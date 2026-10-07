---
title: agrag.ingestion.community.detect_communities
sidebar_label: detect_communities
---

# `agrag.ingestion.community.detect_communities` \{#agrag-ingestion-community-detect_communities}

```python
detect_communities(graph_store:GraphStore, *, vector_store:VectorStore | None, embedder:Embedder, settings:RetrievalSettings, tracer:Tracer | None = None, apply:bool = False, max_cluster_size:int = 10, resolution:float = 1.0, seed:int | None = 3735928559) -> CommunityDetectionReport
```

Detect entity communities via hierarchical Leiden.

Reads every live domain relation across the whole graph, not only one
entity label, because community structure spans entity types. It builds a
weighted edge list and runs hierarchical Leiden off the event loop. With
`apply=True` the run is a full recompute: it deletes every earlier
Community node, MEMBER_OF edge and community vector before it stores the
new ones.

**Parameters:**

- **graph_store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – Where relations and entities are read and communities are
  written.
- **vector_store** (<code>[VectorStore](../../vectordb/base/VectorStore.md) | None</code>) – Holds the community vectors. None skips vector writes.
- **embedder** (<code>[Embedder](../../embedding/base/Embedder.md)</code>) – Embeds the community summaries.
- **settings** (<code>[RetrievalSettings](../../retrieval/settings/RetrievalSettings.md)</code>) – Names the community vector collection.
- **tracer** (<code>Tracer | None</code>) – Opens the detection span. None opens no recorded span.
- **apply** (<code>bool</code>) – Write the communities. False returns a report only.
- **max_cluster_size** (<code>int</code>) – Forwarded to `compute_communities`.
- **resolution** (<code>float</code>) – Forwarded to `compute_communities`.
- **seed** (<code>int | None</code>) – Forwarded to `compute_communities`.

**Returns:**

- <code>[CommunityDetectionReport](../reports/CommunityDetectionReport.md)</code> – A report of every community found, applied or not. A vector store or
- <code>[CommunityDetectionReport](../reports/CommunityDetectionReport.md)</code> – community report failure appears in `failures`.

**Raises:**

- <code>[CommunityDetectionMissingExtraError](CommunityDetectionMissingExtraError.md)</code> – graspologic-native is not
  installed.
