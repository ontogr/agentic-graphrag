---
title: agrag.ingestion.resolve.resolution.resolve_persisted
sidebar_label: resolve_persisted
---

# `agrag.ingestion.resolve.resolution.resolve_persisted` \{#agrag-ingestion-resolve-resolution-resolve_persisted}

```python
resolve_persisted(entities:list[Entity], *, graph_store:GraphStore, embedder:Embedder, entity_labels:Sequence[str], tracer:Tracer | None, max_llm_pairs:int, error_policy:ErrorPolicy, vector_store:VectorStore | None = None, llm_concurrency:int = DEFAULT_LLM_CONCURRENCY) -> tuple[ResolutionResult, list[StageFailure]]
```

Resolve persisted entities against each other.

ANN search bounds the pairs the resolver compares.

**Parameters:**

- **entities** (<code>list\[[Entity](../../../common/data_models/entity/Entity-ref.md)\]</code>) – The persisted entities to compare, all of one label.
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

- <code>[ResolutionResult](../resolver/ResolutionResult.md)</code> – The resolver result, indexed like `entities`, candidate-read
- <code>list\[[StageFailure](../../../common/data_models/stage_failure/StageFailure.md)\]</code> – failures.

**Raises:**

- <code>Exception</code> – A candidate read failed and `error_policy` is RAISE.
