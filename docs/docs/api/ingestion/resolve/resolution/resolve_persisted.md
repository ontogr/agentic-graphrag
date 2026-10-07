---
title: agrag.ingestion.resolve.resolution.resolve_persisted
sidebar_label: resolve_persisted
---

# `agrag.ingestion.resolve.resolution.resolve_persisted` \{#agrag-ingestion-resolve-resolution-resolve_persisted}

```python
resolve_persisted(entities:list[Entity], *, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None, vector_collection:str, entity_labels:Sequence[str], tracer:Tracer | None, max_llm_pairs:int, error_policy:ErrorPolicy) -> tuple[ResolutionResult, list[StageFailure]]
```

Resolve persisted entities against each other.

ANN search bounds the pairs the resolver compares.

**Parameters:**

- **entities** (<code>list\[[Entity](../../../common/data_models/entity/Entity-ref.md)\]</code>) – The persisted entities to compare, all of one label.
- **graph_store** (<code>[GraphStore](../../../graphdb/base/GraphStore.md)</code>) – Where the candidate and neighbor reads run.
- **embedder** (<code>[Embedder](../../../embedding/base/Embedder.md)</code>) – Embeds entity names for candidate search and fuzzy review.
- **vector_store** (<code>[VectorStore](../../../vectordb/base/VectorStore.md) | None</code>) – Optional vector store the candidate search reads.
- **vector_collection** (<code>str</code>) – Collection name for the candidate search.
- **entity_labels** (<code>Sequence\[str\]</code>) – The labels the schema defines.
- **tracer** (<code>Tracer | None</code>) – Traces the resolver.
- **max_llm_pairs** (<code>int</code>) – The most ambiguous pairs per label sent to the LLM.
- **error_policy** (<code>[ErrorPolicy](../../../loaders/corpus/types/ErrorPolicy.md)</code>) – RAISE propagates a failed candidate read; any other
  policy records it and leaves that entity out of this pass.

**Returns:**

- <code>[ResolutionResult](../resolver/ResolutionResult.md)</code> – The resolver result, indexed like `entities`, and one StageFailure
- <code>list\[[StageFailure](../../../common/data_models/stage_failure/StageFailure.md)\]</code> – per entity whose candidate read failed.

**Raises:**

- <code>Exception</code> – A candidate read failed and `error_policy` is RAISE.
