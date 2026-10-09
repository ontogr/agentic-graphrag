---
title: agrag.ingestion.community.embed_communities
sidebar_label: embed_communities
---

# `agrag.ingestion.community.embed_communities` \{#agrag-ingestion-community-embed_communities}

```python
embed_communities(communities:list[Community], *, embedder:Embedder, batch_size:int = _DEFAULT_EMBED_BATCH_SIZE, max_concurrency:int = 4, tracer:Tracer | None = None) -> list[StageFailure]
```

Compute each community's embedding from its report text, in place.

Called after generate_community_reports and before to_node_record(), so
the vector is already present on the very first (and only) write a
replace cycle makes.

Embedder.embed's contract makes no chunking guarantee (see
agrag/embedding/base.py), so at 1M+ entity scale, where a full recompute
can produce 100,000+ communities, this batches the embed() calls itself
rather than passing every community's text in one call.

A batch embed() failure does not block other batches: it is recorded as
one StageFailure per community in that batch, matching the
failure-tolerance shape generate_community_reports already uses. Those
communities keep embedding=None and still get written by
Community.to_node_record(), which omits the embedding property when it
is None, rather than being dropped from the graph.

**Parameters:**

- **communities** (<code>list\[[Community](../../common/data_models/community/Community-ref.md)\]</code>) – The communities to embed, mutated in place.
- **embedder** (<code>[Embedder](../../embedding/base/Embedder.md)</code>) – Computes one vector per community's embedding_text.
- **batch_size** (<code>int</code>) – Communities embedded per embed() call.
- **max_concurrency** (<code>int</code>) – Max concurrent embed calls.
- **tracer** (<code>Tracer | None</code>) – Opens one span per batch.

**Returns:**

- <code>list\[[StageFailure](../../common/data_models/stage_failure/StageFailure.md)\]</code> – One StageFailure per community whose batch embed() call failed.
