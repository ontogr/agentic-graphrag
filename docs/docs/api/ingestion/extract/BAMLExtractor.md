---
title: agrag.ingestion.extract.BAMLExtractor
sidebar_label: BAMLExtractor
---

# `agrag.ingestion.extract.BAMLExtractor` \{#agrag-ingestion-extract-BAMLExtractor}

```python
BAMLExtractor(*, settings:ExtractionLLMSettings | None = None, client:object | None = None, tracer:Tracer | None = None, include_heading_path:bool = True) -> None
```

Bases: <code>[Extractor](Extractor.md)</code>

Extract entities and relations with an LLM through a typed BAML function.

The extractor calls `ExtractEntitiesAndRelations` on the clients in
`ExtractionLLMSettings` and retries failed calls with the backoff from
its configuration. The response type comes from the graph schema, so the
model can return only declared labels and property keys, and it can fill
entity properties. Needs the `llm` extra and a reachable LLM endpoint.

**Parameters:**

- **settings** (<code>[ExtractionLLMSettings](ExtractionLLMSettings.md) | None</code>) – LLM client configuration. Defaults to `ExtractionLLMSettings()`,
  loaded from the environment or `.env`. Ignored when `client` is
  given. An injected client also disables `settings.retry` because
  its caller owns retry behavior.
- **client** (<code>object | None</code>) – An already-built BAML client exposing
  `ExtractEntitiesAndRelations`.
- **tracer** (<code>Tracer | None</code>) – Opens `agrag.extraction.baml` and `agrag.llm.call` spans.
  `None` opens no recorded span.
- **include_heading_path** (<code>bool</code>) – Whether to pass the chunk's heading path as a
  separate `section` line. Offsets still index `chunk.text`; only
  this extractor uses heading context.

**Functions:**

- [**extract**](#agrag-ingestion-extract-BAMLExtractor-extract) – Extract with an LLM call through the configured ClientRegistry.

**Attributes:**

- [**settings**](#agrag-ingestion-extract-BAMLExtractor-settings) –

## `extract` \{#agrag-ingestion-extract-BAMLExtractor-extract}

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract with an LLM call through the configured ClientRegistry.

**Parameters:**

- **chunk** (<code>[Chunk](../../common/data_models/chunk/Chunk-ref.md)</code>) – The chunk to read. Only `chunk.text` and `chunk.id` are used.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – The entity and relation types to extract.

**Returns:**

- <code>[ExtractionResult](../../common/data_models/extraction/ExtractionResult.md)</code> – The normalized entities and relations found in the chunk.

**Raises:**

- <code>[ExtractorMissingExtraError](ExtractorMissingExtraError.md)</code> – The `llm` package extra is not
  installed.
- <code>ValueError</code> – `chunk.id` is `None`.

## `settings` \{#agrag-ingestion-extract-BAMLExtractor-settings}

```python
settings = settings
```
