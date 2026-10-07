---
title: agrag.ingestion.resolved_embeddings.embed_resolved_entities
sidebar_label: embed_resolved_entities
---

# `agrag.ingestion.resolved_embeddings.embed_resolved_entities` \{#agrag-ingestion-resolved_embeddings-embed_resolved_entities}

```python
embed_resolved_entities(entities:list[ResolvedEntity], *, embedder:Embedder, graph_store:GraphStore, vector_store:VectorStore | None, vector_collection:str, error_policy:ErrorPolicy, pending_job_id:UUID | str | None = None) -> list[StageFailure]
```

Write resolved-entity embeddings to the graph and optional vector store.

Graph writes finish before vector-store synchronization because the two
stores cannot share a transaction. A failed sync clears the graph vector,
removes any old mirrored vector, and records `failed` for a later
rebuild pass to retry.

Only entities whose guarded graph write actually matched a live node are
mirrored to the vector store or have their sync status updated. A
concurrent rebuild can replace or delete a ResolvedEntity between
this call reading it and writing its embedding; skipping the unmatched
ones keeps this call from resurrecting a vector, or overwriting a status,
that the concurrent call already owns.
