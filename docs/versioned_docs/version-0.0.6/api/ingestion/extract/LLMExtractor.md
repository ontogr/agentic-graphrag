---
title: agrag.ingestion.extract.LLMExtractor
sidebar_label: LLMExtractor
---

# `agrag.ingestion.extract.LLMExtractor` \{#agrag-ingestion-extract-LLMExtractor}

Bases: <code>ABC</code>

LLM role that may receive entities found by an earlier extractor.

**Functions:**

- [**extract**](#agrag-ingestion-extract-LLMExtractor-extract) – Extract entities and relations from one chunk.

**Attributes:**

- [**max_concurrency**](#agrag-ingestion-extract-LLMExtractor-max_concurrency) (<code>int | None</code>) –

## `extract` \{#agrag-ingestion-extract-LLMExtractor-extract}

```python
extract(chunk:Chunk, schema:GraphSchema, candidates:Sequence[ExtractedEntity] | None = None) -> ExtractionResult
```

Extract entities and relations from one chunk.

**Parameters:**

- **chunk** (<code>[Chunk](../../common/data_models/chunk/Chunk-ref.md)</code>) – The chunk to read.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – The entity and relation types to extract.
- **candidates** (<code>Sequence\[[ExtractedEntity](../../common/data_models/extraction/ExtractedEntity.md)\] | None</code>) – Entities found by an earlier extractor. Escalation may
  pass them for review; an implementation may ignore them.

**Returns:**

- <code>[ExtractionResult](../../common/data_models/extraction/ExtractionResult.md)</code> – The entities and relations found in the chunk.

## `max_concurrency` \{#agrag-ingestion-extract-LLMExtractor-max_concurrency}

```python
max_concurrency: int | None = None
```
