---
title: agrag.ingestion.resolve.resolution.resolve_batch
sidebar_label: resolve_batch
---

# `agrag.ingestion.resolve.resolution.resolve_batch` \{#agrag-ingestion-resolve-resolution-resolve_batch}

```python
resolve_batch(mentions:list[ExtractedEntity], relations:Sequence[ExtractedRelation], chunks_by_id:dict[UUID, Chunk], *, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None, vector_collection:str, entity_labels:Sequence[str], tracer:Tracer | None, max_llm_pairs:int, error_policy:ErrorPolicy, job_id:UUID | str | None = None) -> BatchResolution
```

Resolve one extraction batch against itself and the persisted graph.

The resolver sees the real mentions plus one synthetic mention per
persisted ANN candidate, so a new mention can join a persisted cluster
through one pass. Synthetic mentions never initiate a comparison.

**Parameters:**

- **mentions** (<code>list\[[ExtractedEntity](../../../common/data_models/extraction/ExtractedEntity.md)\]</code>) – The batch's extracted mentions.
- **relations** (<code>Sequence\[[ExtractedRelation](../../../common/data_models/extraction/ExtractedRelation.md)\]</code>) – The relations addressing `mentions`, used as neighbor
  context.
- **chunks_by_id** (<code>dict\[UUID, [Chunk](../../../common/data_models/chunk/Chunk-ref.md)\]</code>) – The batch's chunks, for LLM verification context.
- **graph_store** (<code>[GraphStore](../../../graphdb/base/GraphStore.md)</code>) – Where exact-match, candidate, and neighbor reads run.
- **embedder** (<code>[Embedder](../../../embedding/base/Embedder.md)</code>) – Embeds mention text for candidate search and fuzzy review.
- **vector_store** (<code>[VectorStore](../../../vectordb/base/VectorStore.md) | None</code>) – Optional vector store the candidate search reads.
- **vector_collection** (<code>str</code>) – Collection name for the candidate search.
- **entity_labels** (<code>Sequence\[str\]</code>) – The labels the schema defines.
- **tracer** (<code>Tracer | None</code>) – Opens the phase spans and traces the resolver.
- **max_llm_pairs** (<code>int</code>) – The most ambiguous pairs per label sent to the LLM.
- **error_policy** (<code>[ErrorPolicy](../../../loaders/corpus/types/ErrorPolicy.md)</code>) – RAISE propagates a failed candidate read; any other
  policy records it and leaves that mention unresolved.
- **job_id** (<code>UUID | str | None</code>) – The in-flight Cutover Job's id for the exact-match read.

**Returns:**

- <code>[BatchResolution](BatchResolution.md)</code> – The exact matches, exact groups, resolver result, persisted
- <code>[BatchResolution](BatchResolution.md)</code> – candidates, and candidate-read failures for the batch.

**Raises:**

- <code>Exception</code> – A candidate read failed and `error_policy` is RAISE.
