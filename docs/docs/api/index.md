---
title: API Reference
sidebar_position: 2
---

## `agrag`

Agentic GraphRAG: graph-based RAG with agentic reasoning.

**Modules:**

- [**chunking**](#agrag.chunking) – Chunking helpers for the ingestion layer.
- [**ingestion**](#agrag.ingestion) – The ingestion package.
- [**observability**](#agrag.observability) – OpenTelemetry wiring for the ingestion layer.

### `agrag.chunking`

Chunking helpers for the ingestion layer.

This module isolates the chonkie dependency to one import site, so the rest of the
codebase (and tests) can build a chunker without importing chonkie directly.

**Modules:**

- [**text**](#agrag.chunking.text) – Splits a text Document into Chunks with the chonkie chunker.

**Classes:**

- [**RecursiveChunker**](#agrag.chunking.RecursiveChunker) – Chunker that recursively splits text into smaller chunks, based on the provided RecursiveRules.

**Functions:**

- [**default_chunker**](#agrag.chunking.default_chunker) – Build the default text chunker.

#### `agrag.chunking.RecursiveChunker`

```python
RecursiveChunker(tokenizer:Union[str, TokenizerProtocol] = 'character', chunk_size:int = 2048, rules:RecursiveRules = RecursiveRules(), min_characters_per_chunk:int = 24) -> None
```

Bases: <code>[BaseChunker](#chonkie.chunker.base.BaseChunker)</code>

Chunker that recursively splits text into smaller chunks, based on the provided RecursiveRules.

**Parameters:**

- **tokenizer** (<code>[Union](#typing.Union)\[[str](#str), [TokenizerProtocol](#chonkie.tokenizer.TokenizerProtocol)\]</code>) – Tokenizer to use
- **chunk_size** (<code>[int](#int)</code>) – Maximum size of each chunk.
- **rules** (<code>[RecursiveRules](#chonkie.types.RecursiveRules)</code>) – Recursive rules to use for chunking.
- **min_characters_per_chunk** (<code>[int](#int)</code>) – Minimum number of characters per chunk.

**Functions:**

- [**achunk**](#agrag.chunking.RecursiveChunker.achunk) – Chunk the given text asynchronously.
- [**achunk_batch**](#agrag.chunking.RecursiveChunker.achunk_batch) – Chunk a batch of texts asynchronously.
- [**achunk_document**](#agrag.chunking.RecursiveChunker.achunk_document) – Chunk a document asynchronously.
- [**chunk**](#agrag.chunking.RecursiveChunker.chunk) – Recursively chunk text.
- [**chunk_batch**](#agrag.chunking.RecursiveChunker.chunk_batch) – Chunk a batch of texts.
- [**chunk_document**](#agrag.chunking.RecursiveChunker.chunk_document) – Chunk a document.
- [**from_recipe**](#agrag.chunking.RecursiveChunker.from_recipe) – Create a RecursiveChunker object from a recipe.

**Attributes:**

- [**chunk_size**](#agrag.chunking.RecursiveChunker.chunk_size) –
- [**min_characters_per_chunk**](#agrag.chunking.RecursiveChunker.min_characters_per_chunk) –
- [**rules**](#agrag.chunking.RecursiveChunker.rules) –
- [**sep**](#agrag.chunking.RecursiveChunker.sep) –
- [**tokenizer**](#agrag.chunking.RecursiveChunker.tokenizer) (<code>[AutoTokenizer](#chonkie.tokenizer.AutoTokenizer)</code>) – Get the tokenizer instance.

**Parameters:**

- **tokenizer** (<code>[Union](#typing.Union)\[[str](#str), [TokenizerProtocol](#chonkie.tokenizer.TokenizerProtocol)\]</code>) – Tokenizer to use
- **chunk_size** (<code>[int](#int)</code>) – Maximum size of each chunk.
- **rules** (<code>[RecursiveRules](#chonkie.types.RecursiveRules)</code>) – Recursive rules to use for chunking.
- **min_characters_per_chunk** (<code>[int](#int)</code>) – Minimum number of characters per chunk.

**Raises:**

- <code>[ValueError](#ValueError)</code> – If chunk_size \<=0
- <code>[ValueError](#ValueError)</code> – If min_characters_per_chunk < 1
- <code>[ValueError](#ValueError)</code> – If rules is not a RecursiveRules object.

##### `agrag.chunking.RecursiveChunker.achunk`

```python
achunk(text:str) -> list[Chunk]
```

Chunk the given text asynchronously.

**Parameters:**

- **text** (<code>[str](#str)</code>) – The text to chunk.

**Returns:**

- <code>[list](#list)\[[Chunk](#chonkie.types.Chunk)\]</code> – list\[Chunk\]: A list of Chunks.

##### `agrag.chunking.RecursiveChunker.achunk_batch`

```python
achunk_batch(texts:Sequence[str], show_progress:bool = True) -> list[list[Chunk]]
```

Chunk a batch of texts asynchronously.

**Parameters:**

- **texts** (<code>[Sequence](#typing.Sequence)\[[str](#str)\]</code>) – The texts to chunk.
- **show_progress** (<code>[bool](#bool)</code>) – Whether to show progress.

**Returns:**

- <code>[list](#list)\[[list](#list)\[[Chunk](#chonkie.types.Chunk)\]\]</code> – list\[list[Chunk]\]: A list of lists of Chunks.

##### `agrag.chunking.RecursiveChunker.achunk_document`

```python
achunk_document(document:Document) -> Document
```

Chunk a document asynchronously.

**Parameters:**

- **document** (<code>[Document](#chonkie.types.Document)</code>) – The document to chunk.

**Returns:**

- <code>[Document](#chonkie.types.Document)</code> – The document with chunks populated.

##### `agrag.chunking.RecursiveChunker.chunk`

```python
chunk(text:str) -> list[Chunk]
```

Recursively chunk text.

**Parameters:**

- **text** (<code>[str](#str)</code>) – Text to chunk.

##### `agrag.chunking.RecursiveChunker.chunk_batch`

```python
chunk_batch(texts:Sequence[str], show_progress:bool = True) -> list[list[Chunk]]
```

Chunk a batch of texts.

**Parameters:**

- **texts** (<code>[Sequence](#typing.Sequence)\[[str](#str)\]</code>) – The texts to chunk.
- **show_progress** (<code>[bool](#bool)</code>) – Whether to show progress.

**Returns:**

- <code>[list](#list)\[[list](#list)\[[Chunk](#chonkie.types.Chunk)\]\]</code> – list\[list[Chunk]\]: A list of lists of Chunks.

##### `agrag.chunking.RecursiveChunker.chunk_document`

```python
chunk_document(document:Document) -> Document
```

Chunk a document.

After chunking, non-empty `document.metadata` is shallow-merged into each
chunk's :attr:`~chonkie.types.Chunk.metadata` (chunk keys override on conflict).

**Parameters:**

- **document** (<code>[Document](#chonkie.types.Document)</code>) – The document to chunk.

**Returns:**

- <code>[Document](#chonkie.types.Document)</code> – The document with chunks populated.

##### `agrag.chunking.RecursiveChunker.chunk_size`

```python
chunk_size = chunk_size
```

##### `agrag.chunking.RecursiveChunker.from_recipe`

```python
from_recipe(name:Optional[str] = 'default', lang:Optional[str] = 'en', path:str | PathLike | None = None, tokenizer:Union[str, TokenizerProtocol] = 'character', chunk_size:int = 2048, min_characters_per_chunk:int = 24) -> RecursiveChunker
```

Create a RecursiveChunker object from a recipe.

The recipes are registered in the [Chonkie Recipe Store](https://huggingface.co/datasets/chonkie-ai/recipes). If the recipe is not there, you can create your own recipe and share it with the community!

**Parameters:**

- **name** (<code>[Optional](#typing.Optional)\[[str](#str)\]</code>) – The name of the recipe.
- **lang** (<code>[Optional](#typing.Optional)\[[str](#str)\]</code>) – The language that the recursive chunker should support.
- **path** (<code>[Optional](#typing.Optional)\[[str](#str)\]</code>) – The path to the recipe.
- **tokenizer** (<code>[Union](#typing.Union)\[[str](#str), [TokenizerProtocol](#chonkie.tokenizer.TokenizerProtocol)\]</code>) – The tokenizer to use.
- **chunk_size** (<code>[int](#int)</code>) – The chunk size.
- **min_characters_per_chunk** (<code>[int](#int)</code>) – The minimum number of characters per chunk.

**Returns:**

- **RecursiveChunker** (<code>[RecursiveChunker](#chonkie.chunker.recursive.RecursiveChunker)</code>) – The RecursiveChunker object.

**Raises:**

- <code>[ValueError](#ValueError)</code> – If the recipe is not found.

##### `agrag.chunking.RecursiveChunker.min_characters_per_chunk`

```python
min_characters_per_chunk = min_characters_per_chunk
```

##### `agrag.chunking.RecursiveChunker.rules`

```python
rules = rules
```

##### `agrag.chunking.RecursiveChunker.sep`

```python
sep = '✄'
```

##### `agrag.chunking.RecursiveChunker.tokenizer`

```python
tokenizer: AutoTokenizer
```

Get the tokenizer instance.

#### `agrag.chunking.default_chunker`

```python
default_chunker(chunk_size:int = 1024) -> RecursiveChunker
```

Build the default text chunker.

**Parameters:**

- **chunk_size** (<code>[int](#int)</code>) – The maximum number of characters per chunk.

**Returns:**

- <code>[RecursiveChunker](#chonkie.RecursiveChunker)</code> – A character-based recursive chunker.

#### `agrag.chunking.text`

Splits a text Document into Chunks with the chonkie chunker.

**Functions:**

- [**chunk_document**](#agrag.chunking.text.chunk_document) – Split a document's text into chunks.
- [**iter_chunk_documents**](#agrag.chunking.text.iter_chunk_documents) – Chunk a stream of documents into a flat stream of chunks.

##### `agrag.chunking.text.chunk_document`

```python
chunk_document(document:Document, chunker:RecursiveChunker) -> list[Chunk]
```

Split a document's text into chunks.

This function computes `line_start` and `line_end` from each chunk's character
span,
because the chunker does not report line numbers. It also sets `heading_path` from
the
document's heading outline.

**Parameters:**

- **document** (<code>[Document](#agrag.common.data_models.document.Document)</code>) – The document to split. This function reads only its `text` and
  `heading_outline` fields.
- **chunker** (<code>[RecursiveChunker](#chonkie.RecursiveChunker)</code>) – The chunker to run.

**Returns:**

- <code>[list](#list)\[[Chunk](#agrag.common.data_models.chunk.Chunk)\]</code> – The chunks, in document order.

##### `agrag.chunking.text.iter_chunk_documents`

```python
iter_chunk_documents(documents:Iterator[Document], chunker:RecursiveChunker) -> Iterator[Chunk]
```

Chunk a stream of documents into a flat stream of chunks.

**Parameters:**

- **documents** (<code>[Iterator](#collections.abc.Iterator)\[[Document](#agrag.common.data_models.document.Document)\]</code>) – The documents to chunk, in order.
- **chunker** (<code>[RecursiveChunker](#chonkie.RecursiveChunker)</code>) – The chunker to run on each document.

**Yields:**

- <code>[Chunk](#agrag.common.data_models.chunk.Chunk)</code> – Each chunk, in document then chunk order.

### `agrag.ingestion`

The ingestion package.

**Modules:**

- [**extract**](#agrag.ingestion.extract) – The Extractor interface: reads one Chunk and produces an ExtractionResult.
- [**graph**](#agrag.ingestion.graph) – The public Graph API for ingestion.
- [**resolve**](#agrag.ingestion.resolve) – Entity resolution: deciding which ExtractedEntity mentions are the same thing.

**Classes:**

- [**Graph**](#agrag.ingestion.Graph) – A knowledge graph that a caller can open and add content to.

#### `agrag.ingestion.Graph`

```python
Graph(*, tracer:Tracer | None = None) -> None
```

A knowledge graph that a caller can open and add content to.

**Functions:**

- [**add**](#agrag.ingestion.Graph.add) – Add content to the graph.
- [**open**](#agrag.ingestion.Graph.open) – Open a graph with no setup.

**Parameters:**

- **tracer** (<code>[Tracer](#opentelemetry.trace.Tracer) | None</code>) – A tracer to record spans for every ingest step. Pass `None` to run
  with no tracing.

##### `agrag.ingestion.Graph.add`

```python
add(source:SourcesType | None = None, *, text:str | None = None, documents:Sequence[Document] | None = None, loader:Loader | None = None, error_policy:ErrorPolicy = ErrorPolicy.RAISE, on_progress:Callable[[LoadStats], None] | None = None) -> IngestResult
```

Add content to the graph.

Give exactly one of `source`, `text`, and `documents`.

**Parameters:**

- **source** (<code>[SourcesType](#agrag.ingestion.graph.SourcesType) | None</code>) – A file path, a directory, a glob, or a list of these.
- **text** (<code>[str](#str) | None</code>) – Raw text to add as one document.
- **documents** (<code>[Sequence](#collections.abc.Sequence)\[[Document](#agrag.common.data_models.document.Document)\] | None</code>) – Already-built documents to add directly.
- **loader** (<code>[Loader](#agrag.loaders.corpus.base.Loader) | None</code>) – A loader to use instead of the registry default. Requires a
  single-file `source`; a directory, glob, or list of sources raises an
  error.
- **error_policy** (<code>[ErrorPolicy](#agrag.loaders.corpus.types.ErrorPolicy)</code>) – The action to take on a per-source error.
- **on_progress** (<code>[Callable](#collections.abc.Callable)\[\[[LoadStats](#agrag.loaders.corpus.types.LoadStats)\], None\] | None</code>) – A callback the call runs after each batch.

**Returns:**

- <code>[IngestResult](#agrag.loaders.corpus.types.IngestResult)</code> – A summary of what was added, skipped, and quarantined, plus its chunks.

**Raises:**

- <code>[ValueError](#ValueError)</code> – The call got zero, or more than one, of `source`, `text`,
  and `documents`. Also raised when `loader` is set without
  `source`, or with a source that can match more than one file.
- <code>[UnsupportedFormatError](#UnsupportedFormatError)</code> – No loader is registered for a source's format.
- <code>[MissingExtraError](#MissingExtraError)</code> – A loader is registered for a source's format, but its
  package extra is not installed. This error follows `error_policy`
  instead of always stopping the call.

##### `agrag.ingestion.Graph.open`

```python
open(*, tracer:Tracer | None = None) -> Graph
```

Open a graph with no setup.

**Parameters:**

- **tracer** (<code>[Tracer](#opentelemetry.trace.Tracer) | None</code>) – A tracer to record spans for every ingest step. Pass `None` to
  run with no tracing.

**Returns:**

- <code>[Graph](#agrag.ingestion.graph.Graph)</code> – A ready-to-use graph. This call needs no external service.

#### `agrag.ingestion.extract`

The Extractor interface: reads one Chunk and produces an ExtractionResult.

**Classes:**

- [**BAMLExtractor**](#agrag.ingestion.extract.BAMLExtractor) – Extracts with an LLM, via a BAML function and a runtime ClientRegistry.
- [**EscalatingExtractor**](#agrag.ingestion.extract.EscalatingExtractor) – Runs a cheap primary extractor first, escalating per chunk when it's weak.
- [**ExtractionLLMSettings**](#agrag.ingestion.extract.ExtractionLLMSettings) – Env-backed LLM client config for the extraction role.
- [**Extractor**](#agrag.ingestion.extract.Extractor) – Reads one Chunk and produces the entities and relations it contains.
- [**ExtractorMissingExtraError**](#agrag.ingestion.extract.ExtractorMissingExtraError) – An Extractor needs a package extra that is not installed.
- [**GlinerExtractor**](#agrag.ingestion.extract.GlinerExtractor) – Extracts locally with a GLiNER2.5 model. No network call.

##### `agrag.ingestion.extract.BAMLExtractor`

```python
BAMLExtractor(*, settings:ExtractionLLMSettings | None = None, client:object | None = None) -> None
```

Bases: <code>[Extractor](#agrag.ingestion.extract.Extractor)</code>

Extracts with an LLM, via a BAML function and a runtime ClientRegistry.

**Functions:**

- [**extract**](#agrag.ingestion.extract.BAMLExtractor.extract) – Extract with an LLM call through the configured ClientRegistry.

**Attributes:**

- [**settings**](#agrag.ingestion.extract.BAMLExtractor.settings) –

**Parameters:**

- **settings** (<code>[ExtractionLLMSettings](#agrag.ingestion.extract.ExtractionLLMSettings) | None</code>) – LLM client config. Defaults to `ExtractionLLMSettings()`,
  loaded from the environment/`.env`.
- **client** (<code>[object](#object) | None</code>) – An already-built BAML client object exposing
  `ExtractEntitiesAndRelations`. Tests inject a fake here.

###### `agrag.ingestion.extract.BAMLExtractor.extract`

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract with an LLM call through the configured ClientRegistry.

**Raises:**

- <code>[ExtractorMissingExtraError](#agrag.ingestion.extract.ExtractorMissingExtraError)</code> – The `llm` package extra is not
  installed.

###### `agrag.ingestion.extract.BAMLExtractor.settings`

```python
settings = settings or ExtractionLLMSettings()
```

##### `agrag.ingestion.extract.EscalatingExtractor`

```python
EscalatingExtractor(primary:Extractor, escalate_to:Extractor, *, min_confidence:float = 0.5, min_chunk_words:int = 8) -> None
```

Bases: <code>[Extractor](#agrag.ingestion.extract.Extractor)</code>

Runs a cheap primary extractor first, escalating per chunk when it's weak.

**Functions:**

- [**extract**](#agrag.ingestion.extract.EscalatingExtractor.extract) – Extract with the primary extractor, escalating when it's weak.

**Attributes:**

- [**escalate_to**](#agrag.ingestion.extract.EscalatingExtractor.escalate_to) –
- [**min_chunk_words**](#agrag.ingestion.extract.EscalatingExtractor.min_chunk_words) –
- [**min_confidence**](#agrag.ingestion.extract.EscalatingExtractor.min_confidence) –
- [**primary**](#agrag.ingestion.extract.EscalatingExtractor.primary) –

**Parameters:**

- **primary** (<code>[Extractor](#agrag.ingestion.extract.Extractor)</code>) – Runs first, for every chunk.
- **escalate_to** (<code>[Extractor](#agrag.ingestion.extract.Extractor)</code>) – Runs instead of, never in addition to, the primary's
  result, when escalation triggers. Merging both extractors'
  output would mean reconciling overlapping spans between them,
  which is what entity resolution is for, not extraction.
- **min_confidence** (<code>[float](#float)</code>) – Escalate when the primary's mean entity confidence
  falls below this, among entities that report a confidence.
- **min_chunk_words** (<code>[int](#int)</code>) – Below this word count, a zero-entity result from
  the primary is treated as plausibly correct, not a miss.

###### `agrag.ingestion.extract.EscalatingExtractor.escalate_to`

```python
escalate_to = escalate_to
```

###### `agrag.ingestion.extract.EscalatingExtractor.extract`

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract with the primary extractor, escalating when it's weak.

Returns escalate_to's result outright when escalation triggers, never
a combination of both extractors' results.

###### `agrag.ingestion.extract.EscalatingExtractor.min_chunk_words`

```python
min_chunk_words = min_chunk_words
```

###### `agrag.ingestion.extract.EscalatingExtractor.min_confidence`

```python
min_confidence = min_confidence
```

###### `agrag.ingestion.extract.EscalatingExtractor.primary`

```python
primary = primary
```

##### `agrag.ingestion.extract.ExtractionLLMSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Env-backed LLM client config for the extraction role.

**Attributes:**

- [**clients**](#agrag.ingestion.extract.ExtractionLLMSettings.clients) (<code>[list](#list)\[[LLMClientConfig](#agrag.llm.client_config.LLMClientConfig)\]</code>) – The LLM client(s) to use. One element for a single provider;
  more than one composed per `strategy`.
- [**strategy**](#agrag.ingestion.extract.ExtractionLLMSettings.strategy) (<code>[Literal](#typing.Literal)['single', 'fallback', 'round_robin']</code>) – How to compose multiple clients. Ignored with one client.
- [**retry**](#agrag.ingestion.extract.ExtractionLLMSettings.retry) (<code>[RetryConfig](#agrag.llm.client_config.RetryConfig)</code>) – Retry settings applied to the extraction LLM call.

Env prefix: `EXTRACTION_LLM_`.

**Functions:**

- [**from_openai_compatible_env**](#agrag.ingestion.extract.ExtractionLLMSettings.from_openai_compatible_env) – Build settings from a generic OpenAI-compatible endpoint.

###### `agrag.ingestion.extract.ExtractionLLMSettings.clients`

```python
clients: list[LLMClientConfig]
```

###### `agrag.ingestion.extract.ExtractionLLMSettings.from_openai_compatible_env`

```python
from_openai_compatible_env() -> ExtractionLLMSettings
```

Build settings from a generic OpenAI-compatible endpoint.

Reads `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL_ID` from the
environment or `.env`, so the model name is never hardcoded. Raises
`RuntimeError` when the required variables are not all set.

**Returns:**

- <code>[ExtractionLLMSettings](#agrag.ingestion.extract.ExtractionLLMSettings)</code> – Settings pointing at one `openai-generic` client.

###### `agrag.ingestion.extract.ExtractionLLMSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='EXTRACTION_LLM_', env_file='.env', extra='ignore')
```

###### `agrag.ingestion.extract.ExtractionLLMSettings.retry`

```python
retry: RetryConfig = Field(default_factory=RetryConfig)
```

###### `agrag.ingestion.extract.ExtractionLLMSettings.strategy`

```python
strategy: Literal['single', 'fallback', 'round_robin'] = 'single'
```

##### `agrag.ingestion.extract.Extractor`

Bases: <code>[ABC](#abc.ABC)</code>

Reads one Chunk and produces the entities and relations it contains.

**Functions:**

- [**extract**](#agrag.ingestion.extract.Extractor.extract) – Extract entities and relations from one chunk.

###### `agrag.ingestion.extract.Extractor.extract`

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract entities and relations from one chunk.

**Parameters:**

- **chunk** (<code>[Chunk](#agrag.common.data_models.chunk.Chunk)</code>) – The chunk to read. Only `chunk.text` and `chunk.id` are used.
- **schema** (<code>[GraphSchema](#agrag.common.data_models.graph_schema.GraphSchema)</code>) – The entity/relation types to extract. Every returned entity's
  `label` and relation's `label` must be declared in this schema.

**Returns:**

- <code>[ExtractionResult](#agrag.common.data_models.extraction.ExtractionResult)</code> – The entities and relations this call found, in extraction order.

##### `agrag.ingestion.extract.ExtractorMissingExtraError`

```python
ExtractorMissingExtraError(component:str, extra:str) -> None
```

Bases: <code>[IngestionError](#agrag.loaders.corpus.errors.IngestionError)</code>

An Extractor needs a package extra that is not installed.

**Attributes:**

- [**component**](#agrag.ingestion.extract.ExtractorMissingExtraError.component) – The class name that needs the extra.
- [**extra**](#agrag.ingestion.extract.ExtractorMissingExtraError.extra) – The package extra to install.

###### `agrag.ingestion.extract.ExtractorMissingExtraError.component`

```python
component = component
```

###### `agrag.ingestion.extract.ExtractorMissingExtraError.extra`

```python
extra = extra
```

##### `agrag.ingestion.extract.GlinerExtractor`

```python
GlinerExtractor(*, model_name:str = 'fastino/gliner2.5-small-v1', model:object | None = None) -> None
```

Bases: <code>[Extractor](#agrag.ingestion.extract.Extractor)</code>

Extracts locally with a GLiNER2.5 model. No network call.

**Functions:**

- [**extract**](#agrag.ingestion.extract.GlinerExtractor.extract) – Extract with the local GLiNER2.5 model.

**Attributes:**

- [**model_name**](#agrag.ingestion.extract.GlinerExtractor.model_name) –

**Parameters:**

- **model_name** (<code>[str](#str)</code>) – The checkpoint to load if `model` is not given.
- **model** (<code>[object](#object) | None</code>) – An already-built GLiNER2.5 model. Tests inject a fake here
  to avoid a real model download.

###### `agrag.ingestion.extract.GlinerExtractor.extract`

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract with the local GLiNER2.5 model.

**Raises:**

- <code>[ExtractorMissingExtraError](#agrag.ingestion.extract.ExtractorMissingExtraError)</code> – The `extract` package extra is not
  installed.

###### `agrag.ingestion.extract.GlinerExtractor.model_name`

```python
model_name = model_name
```

#### `agrag.ingestion.graph`

The public Graph API for ingestion.

**Classes:**

- [**Graph**](#agrag.ingestion.graph.Graph) – A knowledge graph that a caller can open and add content to.

**Attributes:**

- [**SourceType**](#agrag.ingestion.graph.SourceType) –
- [**SourcesType**](#agrag.ingestion.graph.SourcesType) –

##### `agrag.ingestion.graph.Graph`

```python
Graph(*, tracer:Tracer | None = None) -> None
```

A knowledge graph that a caller can open and add content to.

**Functions:**

- [**add**](#agrag.ingestion.graph.Graph.add) – Add content to the graph.
- [**open**](#agrag.ingestion.graph.Graph.open) – Open a graph with no setup.

**Parameters:**

- **tracer** (<code>[Tracer](#opentelemetry.trace.Tracer) | None</code>) – A tracer to record spans for every ingest step. Pass `None` to run
  with no tracing.

###### `agrag.ingestion.graph.Graph.add`

```python
add(source:SourcesType | None = None, *, text:str | None = None, documents:Sequence[Document] | None = None, loader:Loader | None = None, error_policy:ErrorPolicy = ErrorPolicy.RAISE, on_progress:Callable[[LoadStats], None] | None = None) -> IngestResult
```

Add content to the graph.

Give exactly one of `source`, `text`, and `documents`.

**Parameters:**

- **source** (<code>[SourcesType](#agrag.ingestion.graph.SourcesType) | None</code>) – A file path, a directory, a glob, or a list of these.
- **text** (<code>[str](#str) | None</code>) – Raw text to add as one document.
- **documents** (<code>[Sequence](#collections.abc.Sequence)\[[Document](#agrag.common.data_models.document.Document)\] | None</code>) – Already-built documents to add directly.
- **loader** (<code>[Loader](#agrag.loaders.corpus.base.Loader) | None</code>) – A loader to use instead of the registry default. Requires a
  single-file `source`; a directory, glob, or list of sources raises an
  error.
- **error_policy** (<code>[ErrorPolicy](#agrag.loaders.corpus.types.ErrorPolicy)</code>) – The action to take on a per-source error.
- **on_progress** (<code>[Callable](#collections.abc.Callable)\[\[[LoadStats](#agrag.loaders.corpus.types.LoadStats)\], None\] | None</code>) – A callback the call runs after each batch.

**Returns:**

- <code>[IngestResult](#agrag.loaders.corpus.types.IngestResult)</code> – A summary of what was added, skipped, and quarantined, plus its chunks.

**Raises:**

- <code>[ValueError](#ValueError)</code> – The call got zero, or more than one, of `source`, `text`,
  and `documents`. Also raised when `loader` is set without
  `source`, or with a source that can match more than one file.
- <code>[UnsupportedFormatError](#UnsupportedFormatError)</code> – No loader is registered for a source's format.
- <code>[MissingExtraError](#MissingExtraError)</code> – A loader is registered for a source's format, but its
  package extra is not installed. This error follows `error_policy`
  instead of always stopping the call.

###### `agrag.ingestion.graph.Graph.open`

```python
open(*, tracer:Tracer | None = None) -> Graph
```

Open a graph with no setup.

**Parameters:**

- **tracer** (<code>[Tracer](#opentelemetry.trace.Tracer) | None</code>) – A tracer to record spans for every ingest step. Pass `None` to
  run with no tracing.

**Returns:**

- <code>[Graph](#agrag.ingestion.graph.Graph)</code> – A ready-to-use graph. This call needs no external service.

##### `agrag.ingestion.graph.SourceType`

```python
SourceType = Union[str, Path]
```

##### `agrag.ingestion.graph.SourcesType`

```python
SourcesType = Union[SourceType, Sequence[SourceType]]
```

#### `agrag.ingestion.resolve`

Entity resolution: deciding which ExtractedEntity mentions are the same thing.

**Classes:**

- [**CandidateSource**](#agrag.ingestion.resolve.CandidateSource) – Narrows which entity pairs resolution compares — the blocking step.
- [**Comparator**](#agrag.ingestion.resolve.Comparator) – One matching strategy a Resolver runs against a candidate pair.
- [**ComparisonVerdict**](#agrag.ingestion.resolve.ComparisonVerdict) – A Comparator's verdict on one entity pair.
- [**ExactMatch**](#agrag.ingestion.resolve.ExactMatch) – Matches when normalized text is identical. Never returns NO_MATCH.
- [**FuzzyMatch**](#agrag.ingestion.resolve.FuzzyMatch) – Matches by string similarity, within a confident-match/distinct band.
- [**InBatchCandidateSource**](#agrag.ingestion.resolve.InBatchCandidateSource) – Blocks by label: only entities sharing a label are ever compared.
- [**LLMVerify**](#agrag.ingestion.resolve.LLMVerify) – Asks an LLM to verify an ambiguous pair. Last resort; never UNCERTAIN.
- [**ResolutionGroup**](#agrag.ingestion.resolve.ResolutionGroup) – One set of ExtractedEntity indices resolution decided are the same entity.
- [**Resolver**](#agrag.ingestion.resolve.Resolver) – Runs an ordered comparator sequence over blocked candidate pairs.

##### `agrag.ingestion.resolve.CandidateSource`

Bases: <code>[ABC](#abc.ABC)</code>

Narrows which entity pairs resolution compares — the blocking step.

**Functions:**

- [**candidates_for**](#agrag.ingestion.resolve.CandidateSource.candidates_for) – Return indices worth comparing against entities[index].

###### `agrag.ingestion.resolve.CandidateSource.candidates_for`

```python
candidates_for(index:int, entities:list[ExtractedEntity]) -> list[int]
```

Return indices worth comparing against entities[index].

**Parameters:**

- **index** (<code>[int](#int)</code>) – The entity to find candidates for.
- **entities** (<code>[list](#list)\[[ExtractedEntity](#agrag.common.data_models.extraction.ExtractedEntity)\]</code>) – The full entity list this call is scoped to.

**Returns:**

- <code>[list](#list)\[[int](#int)\]</code> – Indices into `entities`, excluding `index` itself. Order does
- <code>[list](#list)\[[int](#int)\]</code> – not matter; duplicates are harmless but wasteful.

##### `agrag.ingestion.resolve.Comparator`

Bases: <code>[ABC](#abc.ABC)</code>

One matching strategy a Resolver runs against a candidate pair.

**Functions:**

- [**compare**](#agrag.ingestion.resolve.Comparator.compare) – Compare two entities.

###### `agrag.ingestion.resolve.Comparator.compare`

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Compare two entities.

**Parameters:**

- **a** (<code>[ExtractedEntity](#agrag.common.data_models.extraction.ExtractedEntity)</code>) – The first entity.
- **b** (<code>[ExtractedEntity](#agrag.common.data_models.extraction.ExtractedEntity)</code>) – The second entity.

**Returns:**

- <code>[ComparisonVerdict](#agrag.ingestion.resolve.ComparisonVerdict)</code> – This comparator's verdict. UNCERTAIN defers to the next comparator.

##### `agrag.ingestion.resolve.ComparisonVerdict`

Bases: <code>[StrEnum](#enum.StrEnum)</code>

A Comparator's verdict on one entity pair.

**Attributes:**

- [**MATCH**](#agrag.ingestion.resolve.ComparisonVerdict.MATCH) – The comparator is confident these are the same entity.
- [**NO_MATCH**](#agrag.ingestion.resolve.ComparisonVerdict.NO_MATCH) – The comparator is confident these are different entities.
- [**UNCERTAIN**](#agrag.ingestion.resolve.ComparisonVerdict.UNCERTAIN) – This comparator can't decide; the next one gets a turn.

###### `agrag.ingestion.resolve.ComparisonVerdict.MATCH`

```python
MATCH = 'match'
```

###### `agrag.ingestion.resolve.ComparisonVerdict.NO_MATCH`

```python
NO_MATCH = 'no_match'
```

###### `agrag.ingestion.resolve.ComparisonVerdict.UNCERTAIN`

```python
UNCERTAIN = 'uncertain'
```

##### `agrag.ingestion.resolve.ExactMatch`

Bases: <code>[Comparator](#agrag.ingestion.resolve.Comparator)</code>

Matches when normalized text is identical. Never returns NO_MATCH.

**Functions:**

- [**compare**](#agrag.ingestion.resolve.ExactMatch.compare) – Return MATCH on identical normalized text, else UNCERTAIN.

###### `agrag.ingestion.resolve.ExactMatch.compare`

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Return MATCH on identical normalized text, else UNCERTAIN.

##### `agrag.ingestion.resolve.FuzzyMatch`

```python
FuzzyMatch(*, match_above:float = 0.92, no_match_below:float = 0.7) -> None
```

Bases: <code>[Comparator](#agrag.ingestion.resolve.Comparator)</code>

Matches by string similarity, within a confident-match/distinct band.

**Attributes:**

- [**match_above**](#agrag.ingestion.resolve.FuzzyMatch.match_above) – A similarity score at or above this is a confident match.
- [**no_match_below**](#agrag.ingestion.resolve.FuzzyMatch.no_match_below) – A similarity score below this is a confident non-match.
  A score in between is UNCERTAIN and defers to the next comparator.

**Functions:**

- [**compare**](#agrag.ingestion.resolve.FuzzyMatch.compare) – Return a verdict from token-sort-ratio similarity.

###### `agrag.ingestion.resolve.FuzzyMatch.compare`

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Return a verdict from token-sort-ratio similarity.

###### `agrag.ingestion.resolve.FuzzyMatch.match_above`

```python
match_above = match_above
```

###### `agrag.ingestion.resolve.FuzzyMatch.no_match_below`

```python
no_match_below = no_match_below
```

##### `agrag.ingestion.resolve.InBatchCandidateSource`

Bases: <code>[CandidateSource](#agrag.ingestion.resolve.CandidateSource)</code>

Blocks by label: only entities sharing a label are ever compared.

Scoped to whatever entity list a caller passes to candidates_for — today,
always the current extraction batch. A future graph-backed candidate source
can replace this without changing any Comparator, since comparators only
ever see the pairs a CandidateSource proposes.

**Functions:**

- [**candidates_for**](#agrag.ingestion.resolve.InBatchCandidateSource.candidates_for) – Return every other entity sharing entities[index]'s label.

###### `agrag.ingestion.resolve.InBatchCandidateSource.candidates_for`

```python
candidates_for(index:int, entities:list[ExtractedEntity]) -> list[int]
```

Return every other entity sharing entities[index]'s label.

##### `agrag.ingestion.resolve.LLMVerify`

```python
LLMVerify(*, chunks_by_id:dict[UUID, Chunk], settings:ExtractionLLMSettings | None = None, client:object | None = None) -> None
```

Bases: <code>[Comparator](#agrag.ingestion.resolve.Comparator)</code>

Asks an LLM to verify an ambiguous pair. Last resort; never UNCERTAIN.

Never raises from an LLM-call failure: it resolves to NO_MATCH instead, by
the same fail-safe design as every comparator a Resolver runs — an
ambiguous or failed comparison never merges two entities. A missing package
extra is a configuration error, not an ambiguous judgment call, and is
raised outright instead (see compare's Raises section).

**Functions:**

- [**compare**](#agrag.ingestion.resolve.LLMVerify.compare) – Return the LLM's verdict, or NO_MATCH if the call itself fails.

**Attributes:**

- [**chunks_by_id**](#agrag.ingestion.resolve.LLMVerify.chunks_by_id) –
- [**settings**](#agrag.ingestion.resolve.LLMVerify.settings) –

**Parameters:**

- **chunks_by_id** (<code>[dict](#dict)\[[UUID](#uuid.UUID), [Chunk](#agrag.common.data_models.chunk.Chunk)\]</code>) – Maps a Chunk id to the Chunk, for prompt context.
- **settings** (<code>[ExtractionLLMSettings](#agrag.ingestion.extract.ExtractionLLMSettings) | None</code>) – LLM client config. Defaults to `ExtractionLLMSettings()`.
- **client** (<code>[object](#object) | None</code>) – An already-built BAML client. Tests inject a fake here.

###### `agrag.ingestion.resolve.LLMVerify.chunks_by_id`

```python
chunks_by_id = chunks_by_id
```

###### `agrag.ingestion.resolve.LLMVerify.compare`

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Return the LLM's verdict, or NO_MATCH if the call itself fails.

**Raises:**

- <code>[ExtractorMissingExtraError](#agrag.ingestion.extract.ExtractorMissingExtraError)</code> – The `llm` package extra is not
  installed.

###### `agrag.ingestion.resolve.LLMVerify.settings`

```python
settings = settings or ExtractionLLMSettings()
```

##### `agrag.ingestion.resolve.ResolutionGroup`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

One set of ExtractedEntity indices resolution decided are the same entity.

**Attributes:**

- [**entity_indices**](#agrag.ingestion.resolve.ResolutionGroup.entity_indices) (<code>[list](#list)\[[int](#int)\]</code>) – Indices into the entity list passed to Resolver.resolve.
  A group of one means resolution found no match for that entity.

###### `agrag.ingestion.resolve.ResolutionGroup.entity_indices`

```python
entity_indices: list[int]
```

##### `agrag.ingestion.resolve.Resolver`

```python
Resolver(*, comparators:list[Comparator], candidate_source:CandidateSource) -> None
```

Runs an ordered comparator sequence over blocked candidate pairs.

Groups every pair a comparator confirms as a match into a ResolutionGroup.

**Functions:**

- [**resolve**](#agrag.ingestion.resolve.Resolver.resolve) – Group entities that resolution decided are the same thing.

**Attributes:**

- [**candidate_source**](#agrag.ingestion.resolve.Resolver.candidate_source) –
- [**comparators**](#agrag.ingestion.resolve.Resolver.comparators) –

**Parameters:**

- **comparators** (<code>[list](#list)\[[Comparator](#agrag.ingestion.resolve.Comparator)\]</code>) – Tried in order per candidate pair. The first
  non-UNCERTAIN verdict wins; if every comparator is UNCERTAIN,
  the pair does not merge.
- **candidate_source** (<code>[CandidateSource](#agrag.ingestion.resolve.CandidateSource)</code>) – Narrows which pairs get compared at all.

###### `agrag.ingestion.resolve.Resolver.candidate_source`

```python
candidate_source = candidate_source
```

###### `agrag.ingestion.resolve.Resolver.comparators`

```python
comparators = comparators
```

###### `agrag.ingestion.resolve.Resolver.resolve`

```python
resolve(entities:list[ExtractedEntity]) -> list[ResolutionGroup]
```

Group entities that resolution decided are the same thing.

**Parameters:**

- **entities** (<code>[list](#list)\[[ExtractedEntity](#agrag.common.data_models.extraction.ExtractedEntity)\]</code>) – The entities to resolve. Only entities passed in the
  same call are ever compared against each other — resolving
  against previously-resolved entities from an earlier call is
  not supported by this Resolver.

**Returns:**

- <code>[list](#list)\[[ResolutionGroup](#agrag.ingestion.resolve.ResolutionGroup)\]</code> – One ResolutionGroup per distinct entity found. Every input index
- <code>[list](#list)\[[ResolutionGroup](#agrag.ingestion.resolve.ResolutionGroup)\]</code> – appears in exactly one group.

### `agrag.observability`

OpenTelemetry wiring for the ingestion layer.

This module imports only `opentelemetry-api`. The SDK and exporters stay in
the optional `observability` extra and are never imported here; a caller
wires them before opening a graph. The tracer is constructor-injected, never
ambient.

**Functions:**

- [**get_tracer**](#agrag.observability.get_tracer) – Return a usable tracer.
- [**traced**](#agrag.observability.traced) – Wrap a call in a span on the given tracer.

#### `agrag.observability.get_tracer`

```python
get_tracer(tracer:Tracer | None) -> Tracer
```

Return a usable tracer.

**Parameters:**

- **tracer** (<code>[Tracer](#opentelemetry.trace.Tracer) | None</code>) – A caller-supplied tracer, or `None` to use OpenTelemetry's
  global no-op tracer.

**Returns:**

- <code>[Tracer](#opentelemetry.trace.Tracer)</code> – The supplied tracer, or the global no-op tracer when the caller passed `None`.

#### `agrag.observability.traced`

```python
traced(tracer:Tracer | None) -> Callable[[Callable], Callable]
```

Wrap a call in a span on the given tracer.

Use this at each pipeline call site (loader, chunker). It works on both
sync and async functions; the span name is the wrapped callable's
qualified name.

**Parameters:**

- **tracer** (<code>[Tracer](#opentelemetry.trace.Tracer) | None</code>) – The tracer to record on, or `None` for a no-op span.

**Returns:**

- <code>[Callable](#typing.Callable)\[\[[Callable](#typing.Callable)\], [Callable](#typing.Callable)\]</code> – A decorator that wraps the target callable in a span.
