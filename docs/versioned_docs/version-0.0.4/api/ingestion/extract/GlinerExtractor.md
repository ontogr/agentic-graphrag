---
title: agrag.ingestion.extract.GlinerExtractor
sidebar_label: GlinerExtractor
---

# `agrag.ingestion.extract.GlinerExtractor` \{#agrag-ingestion-extract-GlinerExtractor}

```python
GlinerExtractor(*, model_name:str = 'fastino/gliner2.5-small-v1', model:object | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Extractor](Extractor.md)</code>

Extracts locally with a GLiNER2.5 model. No network call.

**Functions:**

- [**extract**](#agrag-ingestion-extract-GlinerExtractor-extract) – Extract with the local GLiNER2.5 model.

**Attributes:**

- [**model_name**](#agrag-ingestion-extract-GlinerExtractor-model_name) –

**Parameters:**

- **model_name** (<code>str</code>) – The checkpoint to load if `model` is not given.
- **model** (<code>object | None</code>) – An already-built GLiNER2.5 model. Tests inject a fake here
  to avoid a real model download.
- **tracer** (<code>Tracer | None</code>) – Opens `agrag.extraction.gliner` and
  `agrag.extraction.model_load` spans. `None` opens no
  recorded span.

## `extract` \{#agrag-ingestion-extract-GlinerExtractor-extract}

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract with the local GLiNER2.5 model.

**Raises:**

- <code>[ExtractorMissingExtraError](ExtractorMissingExtraError.md)</code> – The `extract` package extra is not
  installed.
- <code>ValueError</code> – `chunk.id` is `None`.

## `model_name` \{#agrag-ingestion-extract-GlinerExtractor-model_name}

```python
model_name = model_name
```
