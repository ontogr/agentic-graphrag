---
title: agrag.ingestion.resolve.resolution.resolve_created
sidebar_label: resolve_created
---

# `agrag.ingestion.resolve.resolution.resolve_created` \{#agrag-ingestion-resolve-resolution-resolve_created}

```python
resolve_created(created:list[Entity], *, graph_store:GraphStore, embedder:Embedder, entity_labels:Sequence[str], tracer:Tracer | None, max_llm_pairs:int, error_policy:ErrorPolicy, vector_store:VectorStore | None = None, llm_concurrency:int = DEFAULT_LLM_CONCURRENCY) -> tuple[list[Entity], ResolutionResult, list[StageFailure]]
```

Resolve newly committed entities against everything committed.

Each created entity looks up its committed candidates, so a near-duplicate
that another job committed first becomes a pair. Only the created entities
start a comparison; the candidates they find are compared with them and
never with each other. When the search finds no candidate for any entity
and the label holds few committed entities, all of them are candidates.

**Parameters:**

- **created** (<code>list\[[Entity](../../../common/data_models/entity/Entity-ref.md)\]</code>) – The committed entities to resolve.
- **graph_store** (<code>[GraphStore](../../../graphdb/base/GraphStore.md)</code>) – Where the candidate and neighbor reads run.
- **embedder** (<code>[Embedder](../../../embedding/base/Embedder.md)</code>) – Embeds entity names for candidate search and fuzzy review.
- **vector_store** (<code>VectorStore | None</code>) – External dense candidate index. None uses graph indexes.
- **entity_labels** (<code>Sequence\[str\]</code>) – The labels the schema defines.
- **tracer** (<code>Tracer | None</code>) – Traces the resolver.
- **max_llm_pairs** (<code>int</code>) – The most ambiguous pairs per label sent to the LLM.
- **llm_concurrency** (<code>int</code>) – Maximum simultaneous verification requests.
- **error_policy** (<code>[ErrorPolicy](../../../loaders/types/ErrorPolicy.md)</code>) – RAISE propagates candidate-read failures.
  Other policies record candidate-read failures and leave those
  entities out of this pass. Telemetry reads never change the result.

**Returns:**

- <code>list\[[Entity](../../../common/data_models/entity/Entity-ref.md)\]</code> – The created entities followed by the candidates they found, the
- <code>[ResolutionResult](../resolver/ResolutionResult.md)</code> – resolver result indexed like that list, and candidate-read failures.

**Raises:**

- <code>Exception</code> – A candidate read failed and `error_policy` is RAISE.
