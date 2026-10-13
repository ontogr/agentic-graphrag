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
`model` is passed. Needs the `extract` extra.

One model call reads the whole schema: every entity type and every relation,
each with its description. Entities need `settings.entity_threshold`.
Relations need `settings.relation_threshold` and must match a pattern of
the schema, where a pattern also accepts the child types of its labels. When
the model returns the same words under a parent type and a child type, the
label with the higher score is kept. Every kept entity and relation carries
its confidence.

The extractor reports what it dropped as candidates in the result: relations
below the threshold, that match no pattern, or whose endpoint is not a kept
entity. With `settings.candidates_enabled` it also makes a second model
call at `settings.band_floor` and reports entity spans that score between
that floor and the entity threshold and do not overlap a kept entity.

The model reports spans and types only, so extracted entities carry no
property values. The result sets `needs_properties` when a kept entity has
a type that declares properties. Chunks of the default size fit the model in
one pass.

**Parameters:**

- **settings** (<code>[ExtractionSettings](../settings/ExtractionSettings.md) | None</code>) – Model name, data type and thresholds. Defaults to
  `ExtractionSettings()`, loaded from the environment or `.env`.
- **model** (<code>object | None</code>) – An already-built GLiNER2.5 model.
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
