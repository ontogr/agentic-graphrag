---
title: agrag.ingestion.extract.BAMLExtractor
sidebar_label: BAMLExtractor
---

# `agrag.ingestion.extract.BAMLExtractor` \{#agrag-ingestion-extract-BAMLExtractor}

```python
BAMLExtractor(*, settings:ExtractionLLMSettings | None = None, client:object | None = None, tracer:Tracer | None = None, include_heading_path:bool = True) -> None
```

Bases: <code>[Extractor](Extractor.md)</code>

Extracts with an LLM, via a BAML function and a runtime ClientRegistry.

**Functions:**

- [**extract**](#agrag-ingestion-extract-BAMLExtractor-extract) – Extract with an LLM call through the configured ClientRegistry.

**Attributes:**

- [**settings**](#agrag-ingestion-extract-BAMLExtractor-settings) –

**Parameters:**

- **settings** (<code>[ExtractionLLMSettings](ExtractionLLMSettings.md) | None</code>) – LLM client config. Defaults to `ExtractionLLMSettings()`,
  loaded from the environment/`.env`. Ignored when `client`
  is given: an injected client also disables `settings.retry`,
  since a caller building its own client is assumed to own its
  own retry behavior too.
- **client** (<code>object | None</code>) – An already-built BAML client object exposing
  `ExtractEntitiesAndRelations`. Tests inject a fake here.
- **tracer** (<code>Tracer | None</code>) – Opens `agrag.extraction.baml` and the nested
  `agrag.llm.call` spans. `None` opens no recorded span.
- **include_heading_path** (<code>bool</code>) – Whether to give the model the heading path of the
  chunk as a separate `section` line above the text. Offsets still
  index `chunk.text`. Only this extractor uses heading context.

## `extract` \{#agrag-ingestion-extract-BAMLExtractor-extract}

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract with an LLM call through the configured ClientRegistry.

**Raises:**

- <code>[ExtractorMissingExtraError](ExtractorMissingExtraError.md)</code> – The `llm` package extra is not
  installed.
- <code>ValueError</code> – `chunk.id` is `None`.

## `settings` \{#agrag-ingestion-extract-BAMLExtractor-settings}

```python
settings = settings
```
