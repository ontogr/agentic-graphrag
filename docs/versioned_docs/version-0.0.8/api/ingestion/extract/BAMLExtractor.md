---
title: agrag.ingestion.extract.BAMLExtractor
sidebar_label: BAMLExtractor
---

# `agrag.ingestion.extract.BAMLExtractor` \{#agrag-ingestion-extract-BAMLExtractor}

```python
BAMLExtractor(*, settings:ExtractionLLMSettings | None = None, client:object | None = None, tracer:Tracer | None = None, include_heading_path:bool = True) -> None
```

Bases: <code>[LLMExtractor](LLMExtractor.md)</code>

Extract entities and relations with an LLM through a typed BAML function.

The extractor calls `ExtractEntitiesAndRelations` on the clients in
`ExtractionLLMSettings` and retries failed calls with the backoff from
its configuration. The model sees each label with its description through
the enum values. The model answers with labels and names only. The
extractor finds each name in the chunk text and drops a name that is not
there. The response type comes from the graph schema, so the model can
return only declared labels. When an entity type declares properties, the
model also fills a `properties` value for each entity. A reply that holds
no JSON answer raises `UnparsableExtractionError`. Needs the `llm`
extra and a reachable LLM endpoint.

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
  separate `section` line. The heading is never searched for
  mentions, so an entity found only in the heading is dropped; only
  this extractor uses heading context.

**Functions:**

- [**extract**](#agrag-ingestion-extract-BAMLExtractor-extract) – Extract with an LLM call through the configured ClientRegistry.

**Attributes:**

- [**include_heading_path**](#agrag-ingestion-extract-BAMLExtractor-include_heading_path) (<code>bool</code>) – Whether the chunk's heading path is sent to the model as context.
- [**max_concurrency**](#agrag-ingestion-extract-BAMLExtractor-max_concurrency) (<code>int | None</code>) –
- [**settings**](#agrag-ingestion-extract-BAMLExtractor-settings) –

## `extract` \{#agrag-ingestion-extract-BAMLExtractor-extract}

```python
extract(chunk:Chunk, schema:GraphSchema, candidates:Sequence[ExtractedEntity] | None = None) -> ExtractionResult
```

Extract with an LLM call through the configured ClientRegistry.

**Parameters:**

- **chunk** (<code>[Chunk](../../common/data_models/chunk/Chunk-ref.md)</code>) – The chunk to read. Only `chunk.text` and `chunk.id` are used.
- **schema** (<code>[GraphSchema](../../common/data_models/graph_schema/GraphSchema.md)</code>) – The entity and relation types to extract.
- **candidates** (<code>Sequence\[[ExtractedEntity](../../common/data_models/extraction/ExtractedEntity.md)\] | None</code>) – Entities an earlier extractor found. They are listed in
  the prompt for the model to check. None or empty gives the
  prompt without that list.

**Returns:**

- <code>[ExtractionResult](../../common/data_models/extraction/ExtractionResult.md)</code> – The entities and relations found in the chunk. An empty result means
- <code>[ExtractionResult](../../common/data_models/extraction/ExtractionResult.md)</code> – the model answered with no entities or relations.

**Raises:**

- <code>[ExtractorMissingExtraError](ExtractorMissingExtraError.md)</code> – The `llm` package extra is not
  installed.
- <code>[UnparsableExtractionError](UnparsableExtractionError.md)</code> – The reply holds no JSON answer, such as
  prose or a cut-off object.
- <code>ValueError</code> – `chunk.id` is `None`.

## `include_heading_path` \{#agrag-ingestion-extract-BAMLExtractor-include_heading_path}

```python
include_heading_path: bool
```

Whether the chunk's heading path is sent to the model as context.

## `max_concurrency` \{#agrag-ingestion-extract-BAMLExtractor-max_concurrency}

```python
max_concurrency: int | None = None
```

## `settings` \{#agrag-ingestion-extract-BAMLExtractor-settings}

```python
settings = settings
```
