---
title: agrag.ingestion.extract.GlinerExtractor
sidebar_label: GlinerExtractor
---

# `agrag.ingestion.extract.GlinerExtractor` \{#agrag-ingestion-extract-GlinerExtractor}

```python
GlinerExtractor(*, settings:ExtractionSettings | None = None, model:object | None = None, tracer:Tracer | None = None) -> None
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
It asks for confidence and spans, and applies the configured entity and
per-label thresholds.

**Parameters:**

- **settings** (<code>[ExtractionSettings](../settings/ExtractionSettings.md) | None</code>) – The checkpoint, precision and score thresholds. `None`
  reads `ExtractionSettings` from the environment and `.env`.
- **model** (<code>object | None</code>) – An already-built GLiNER2.5 model. The checkpoint and precision
  settings do not apply to this model.
- **tracer** (<code>Tracer | None</code>) – Opens `agrag.extraction.gliner` and
  `agrag.extraction.model_load` spans. `None` opens no recorded
  span.

**Attributes:**

- [**settings**](#agrag-ingestion-extract-GlinerExtractor-settings) – The checkpoint, precision and thresholds used by extraction.

**Functions:**

- [**extract**](#agrag-ingestion-extract-GlinerExtractor-extract) – Extract with the local GLiNER2.5 model.

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

## `settings` \{#agrag-ingestion-extract-GlinerExtractor-settings}

```python
settings = settings if settings is not None else ExtractionSettings()
```
