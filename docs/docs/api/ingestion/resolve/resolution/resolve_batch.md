---
title: agrag.ingestion.resolve.resolution.resolve_batch
sidebar_label: resolve_batch
---

# `agrag.ingestion.resolve.resolution.resolve_batch` \{#agrag-ingestion-resolve-resolution-resolve_batch}

```python
resolve_batch(mentions:list[ExtractedEntity], relations:Sequence[ExtractedRelation], chunks_by_id:dict[UUID, Chunk], *, graph_store:GraphStore, embedder:Embedder, entity_labels:Sequence[str], tracer:Tracer | None, max_llm_pairs:int, error_policy:ErrorPolicy, job_id:UUID | str | None = None, llm_concurrency:int = 2, on_progress:Callable[[int, int, float], None] | None = None) -> BatchResolution
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
- **entity_labels** (<code>Sequence\[str\]</code>) – The labels the schema defines.
- **tracer** (<code>Tracer | None</code>) – Opens the phase spans and traces the resolver.
- **max_llm_pairs** (<code>int</code>) – The most ambiguous pairs per label sent to the LLM.
- **llm_concurrency** (<code>int</code>) – Maximum simultaneous verification requests.
- **on_progress** (<code>Callable\\[[int, int, float\], None\] | None</code>) – Receives completed batches, total batches and elapsed seconds.
- **error_policy** (<code>[ErrorPolicy](../../../loaders/types/ErrorPolicy.md)</code>) – RAISE propagates candidate and telemetry read failures.
  Other policies record candidate-read failures and leave those
  mentions unresolved; telemetry-read failures are reported without
  changing comparisons.
- **job_id** (<code>UUID | str | None</code>) – The in-flight Cutover Job's id for the exact-match read.

**Returns:**

- <code>[BatchResolution](BatchResolution.md)</code> – The exact matches, exact groups, resolver result, persisted
- <code>[BatchResolution](BatchResolution.md)</code> – candidates, candidate-read failures, and any telemetry-read failure.

**Raises:**

- <code>Exception</code> – A candidate or telemetry read failed and `error_policy`
  is RAISE.
