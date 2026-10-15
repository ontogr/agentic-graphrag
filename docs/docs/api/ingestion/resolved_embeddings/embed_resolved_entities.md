---
title: agrag.ingestion.resolved_embeddings.embed_resolved_entities
sidebar_label: embed_resolved_entities
---

# `agrag.ingestion.resolved_embeddings.embed_resolved_entities` \{#agrag-ingestion-resolved_embeddings-embed_resolved_entities}

```python
embed_resolved_entities(entities:list[ResolvedEntity], *, embedder:Embedder, graph_store:GraphStore, error_policy:ErrorPolicy, pending_job_id:UUID | str | None = None, deferred:DeferredWrites | None = None) -> list[StageFailure]
```

Write resolved-entity embeddings to the graph and record their sync status.

A failed write clears the graph vector and records `failed` for a later
rebuild pass to retry.

Only entities whose guarded graph write actually matched a live node have
their sync status updated. A
concurrent rebuild can replace or delete a ResolvedEntity between
this call reading it and writing its embedding; skipping the unmatched
ones keeps this call from resurrecting a vector, or overwriting a status,
that the concurrent call already owns. Under a job, an embedding over a
committed node is deferred to the commit and is not written yet.

**Raises:**

- <code>ValueError</code> – `pending_job_id` is set and `deferred` is None.
