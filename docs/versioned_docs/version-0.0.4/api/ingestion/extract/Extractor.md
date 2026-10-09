---
title: agrag.ingestion.extract.Extractor
sidebar_label: Extractor
---

# `agrag.ingestion.extract.Extractor` \{#agrag-ingestion-extract-Extractor}

Bases: <code>ABC</code>

Reads one Chunk and produces the entities and relations it contains.

**Functions:**

- [**extract**](#agrag-ingestion-extract-Extractor-extract) – Extract entities and relations from one chunk.

## `extract` \{#agrag-ingestion-extract-Extractor-extract}

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract entities and relations from one chunk.

**Parameters:**

- **chunk** (<code>[Chunk](../../common/data_models/chunk/Chunk-ref.md)</code>) – The chunk to read. Only `chunk.text` and `chunk.id` are used.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – The entity/relation types to extract. Every returned entity's
  `label` and relation's `label` must be declared in this schema.

**Returns:**

- <code>[ExtractionResult](../../common/data_models/extraction/ExtractionResult.md)</code> – The entities and relations this call found, in extraction order.
