---
title: agrag.ingestion.extract.GlinerExtractor
sidebar_label: GlinerExtractor
---

# `agrag.ingestion.extract.GlinerExtractor` \{#agrag-ingestion-extract-GlinerExtractor}

```python
GlinerExtractor(*, model_name:str = 'fastino/gliner2.5-small-v1', model:object | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Extractor](Extractor.md)</code>

Extracts entities and relations with a local GLiNER2.5 model.

The model runs in this process, so extraction needs no LLM key. It loads on
first use and one load serves concurrent calls. Inference calls run one at a
time on one worker thread. A call cancelled while it waits for its turn never
starts, and one cancelled mid-inference leaves the next call waiting until the
inference ends. The first load downloads the weights from Hugging Face unless
`model` is passed. GLiNER reports entity spans and types, so extracted
entities carry no property values. Needs the `extract` extra.

**Parameters:**

- **model_name** (<code>str</code>) – Checkpoint to load when `model` is not provided.
- **model** (<code>object | None</code>) – An already-built GLiNER2.5 model.
- **tracer** (<code>Tracer | None</code>) – Opens `agrag.extraction.gliner` and
  `agrag.extraction.model_load` spans. `None` opens no recorded
  span.

**Functions:**

- [**extract**](#agrag-ingestion-extract-GlinerExtractor-extract) – Extract with the local GLiNER2.5 model.

**Attributes:**

- [**max_concurrency**](#agrag-ingestion-extract-GlinerExtractor-max_concurrency) –
- [**model_name**](#agrag-ingestion-extract-GlinerExtractor-model_name) –

## `extract` \{#agrag-ingestion-extract-GlinerExtractor-extract}

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract with the local GLiNER2.5 model.

**Parameters:**

- **chunk** (<code>[Chunk](../../common/data_models/chunk/Chunk-ref.md)</code>) – The chunk to read. Only `chunk.text` and `chunk.id` are used.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – The entity and relation types to extract.

**Returns:**

- <code>[ExtractionResult](../../common/data_models/extraction/ExtractionResult.md)</code> – The normalized entities and relations found in the chunk.

**Raises:**

- <code>[ExtractorMissingExtraError](ExtractorMissingExtraError.md)</code> – The `extract` package extra is not
  installed.
- <code>ValueError</code> – `chunk.id` is `None`.

## `max_concurrency` \{#agrag-ingestion-extract-GlinerExtractor-max_concurrency}

```python
max_concurrency = 1
```

## `model_name` \{#agrag-ingestion-extract-GlinerExtractor-model_name}

```python
model_name = model_name
```
