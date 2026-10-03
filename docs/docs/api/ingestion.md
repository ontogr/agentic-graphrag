---
title: agrag.ingestion
sidebar_position: 8
---

## `agrag.ingestion` \{#agrag-ingestion}

The ingestion package.

**Modules:**

- [**community**](#agrag-ingestion-community) – Community detection: hierarchical Leiden over the entity graph.
- [**extract**](#agrag-ingestion-extract) – The Extractor interface: reads one Chunk and produces an ExtractionResult.
- [**graph**](#agrag-ingestion-graph) – The public Graph API for ingestion.
- [**merge**](#agrag-ingestion-merge) – Merge mechanics: computing how a resolved group of mentions and entities combine.
- [**reports**](#agrag-ingestion-reports) – Reports returned by Graph pipeline operations.
- [**resolve**](#agrag-ingestion-resolve) – Entity resolution public API.
- [**resolved_embeddings**](#agrag-ingestion-resolved_embeddings) – Embedding and vector synchronization for resolved-entities.
- [**resolved_entities**](#agrag-ingestion-resolved_entities) – Non-destructive match persistence and resolved-entity computation.
- [**settings**](#agrag-ingestion-settings) – Configuration for the Cutover Job crash-recovery machine.
- [**stats**](#agrag-ingestion-stats) – Per-stage observability types for the ingestion pipeline.

**Classes:**

- [**AddResult**](#agrag-ingestion-AddResult) – Graph.add()'s return type — one summary per pipeline stage.
- [**BAMLExtractor**](#agrag-ingestion-BAMLExtractor) – Extracts entities and relations with an LLM through a typed BAML function.
- [**CommunityDetectionReport**](#agrag-ingestion-CommunityDetectionReport) – Report from Graph.detect_communities().
- [**ConsolidationReport**](#agrag-ingestion-ConsolidationReport) – Report from Graph.consolidate().
- [**EscalatingExtractor**](#agrag-ingestion-EscalatingExtractor) – Runs a cheap extractor on every chunk and a stronger one on weak results.
- [**ExtractionLLMSettings**](#agrag-ingestion-ExtractionLLMSettings) – Env-backed LLM client config for the extraction role.
- [**Extractor**](#agrag-ingestion-Extractor) – Reads one chunk and returns the entities and relations it contains.
- [**ExtractorMissingExtraError**](#agrag-ingestion-ExtractorMissingExtraError) – An Extractor needs a package extra that is not installed.
- [**GlinerExtractor**](#agrag-ingestion-GlinerExtractor) – Extracts entities and relations with a local GLiNER2.5 model.
- [**Graph**](#agrag-ingestion-Graph) – A knowledge graph that a caller can open and add content to.
- [**ReevaluationReport**](#agrag-ingestion-ReevaluationReport) – Report from Graph.reevaluate().
- [**UpdateResult**](#agrag-ingestion-UpdateResult) – Summary of an update or soft deletion.

### `agrag.ingestion.AddResult` \{#agrag-ingestion-AddResult}

Bases: <code>BaseModel</code>

Graph.add()'s return type — one summary per pipeline stage.

**Attributes:**

- [**ingestion**](#agrag-ingestion-AddResult-ingestion) (<code>[IngestStats](#agrag-ingestion-stats-IngestStats)</code>) – Ingestion-stage results.
- [**chunking**](#agrag-ingestion-AddResult-chunking) (<code>[ChunkingStats](#agrag-ingestion-stats-ChunkingStats)</code>) – The chunker each document got and the chunks it made.
- [**extraction**](#agrag-ingestion-AddResult-extraction) (<code>[ExtractionStats](#agrag-ingestion-stats-ExtractionStats)</code>) – Extractor output across every chunk this call
  processed.
- [**resolution**](#agrag-ingestion-AddResult-resolution) (<code>[ResolutionStats](#agrag-ingestion-stats-ResolutionStats)</code>) – Resolution's tier-by-tier match counts.
- [**merge**](#agrag-ingestion-AddResult-merge) (<code>[MergeStats](#agrag-ingestion-stats-MergeStats)</code>) – What merge mechanics did with resolution's groups.
- [**storage**](#agrag-ingestion-AddResult-storage) (<code>[StorageStats](#agrag-ingestion-stats-StorageStats)</code>) – What made it to GraphStore, and what didn't.
- [**chunks**](#agrag-ingestion-AddResult-chunks) (<code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code>) – Every Chunk this call produced. Empty unless
  return_chunks=True — holding full chunk text for a large
  corpus is a real memory cost most callers don't need paid
  for.

#### `agrag.ingestion.AddResult.chunking` \{#agrag-ingestion-AddResult-chunking}

```python
chunking: ChunkingStats = Field(default_factory=ChunkingStats)
```

#### `agrag.ingestion.AddResult.chunks` \{#agrag-ingestion-AddResult-chunks}

```python
chunks: list[Chunk] = Field(default_factory=list)
```

#### `agrag.ingestion.AddResult.documents` \{#agrag-ingestion-AddResult-documents}

```python
documents: int
```

Proxy to ingestion.documents for backward compatibility.

#### `agrag.ingestion.AddResult.extraction` \{#agrag-ingestion-AddResult-extraction}

```python
extraction: ExtractionStats = Field(default_factory=ExtractionStats)
```

#### `agrag.ingestion.AddResult.ingestion` \{#agrag-ingestion-AddResult-ingestion}

```python
ingestion: IngestStats = Field(default_factory=IngestStats)
```

#### `agrag.ingestion.AddResult.merge` \{#agrag-ingestion-AddResult-merge}

```python
merge: MergeStats = Field(default_factory=MergeStats)
```

#### `agrag.ingestion.AddResult.quarantined` \{#agrag-ingestion-AddResult-quarantined}

```python
quarantined: int
```

Proxy to ingestion.quarantined for backward compatibility.

#### `agrag.ingestion.AddResult.quarantined_items` \{#agrag-ingestion-AddResult-quarantined_items}

```python
quarantined_items: list[StageFailure]
```

Proxy to ingestion.quarantined_items for backward compatibility.

#### `agrag.ingestion.AddResult.resolution` \{#agrag-ingestion-AddResult-resolution}

```python
resolution: ResolutionStats = Field(default_factory=ResolutionStats)
```

#### `agrag.ingestion.AddResult.skipped` \{#agrag-ingestion-AddResult-skipped}

```python
skipped: int
```

Proxy to ingestion.skipped for backward compatibility.

#### `agrag.ingestion.AddResult.sources` \{#agrag-ingestion-AddResult-sources}

```python
sources: int
```

Proxy to ingestion.sources for backward compatibility.

#### `agrag.ingestion.AddResult.storage` \{#agrag-ingestion-AddResult-storage}

```python
storage: StorageStats = Field(default_factory=StorageStats)
```

### `agrag.ingestion.BAMLExtractor` \{#agrag-ingestion-BAMLExtractor}

```python
BAMLExtractor(*, settings:ExtractionLLMSettings | None = None, client:object | None = None, tracer:Tracer | None = None, include_heading_path:bool = True) -> None
```

Bases: <code>[Extractor](#agrag-ingestion-extract-Extractor)</code>

Extracts entities and relations with an LLM through a typed BAML function.

The extractor calls `ExtractEntitiesAndRelations` on the clients in
`ExtractionLLMSettings` and retries failed calls with the settings' backoff.
The response type comes from the graph schema, so the model can return only
declared labels and property keys, and it can fill entity properties. Needs
the `llm` extra and a reachable LLM endpoint.

**Parameters:**

- **settings** (<code>[ExtractionLLMSettings](#agrag-ingestion-extract-ExtractionLLMSettings) | None</code>) – LLM client config. Defaults to `ExtractionLLMSettings()`,
  loaded from the environment or `.env`. Ignored when `client` is
  given; an injected client also disables `settings.retry` because
  its caller owns retry behavior.
- **client** (<code>object | None</code>) – An already-built BAML client exposing
  `ExtractEntitiesAndRelations`.
- **tracer** (<code>Tracer | None</code>) – Opens `agrag.extraction.baml` and `agrag.llm.call` spans.
  `None` opens no recorded span.
- **include_heading_path** (<code>bool</code>) – Whether to pass the chunk's heading path as a
  separate `section` line. Offsets still index `chunk.text`; only
  this extractor uses heading context.

**Functions:**

- [**extract**](#agrag-ingestion-BAMLExtractor-extract) – Extract with an LLM call through the configured ClientRegistry.

**Attributes:**

- [**settings**](#agrag-ingestion-BAMLExtractor-settings) –

#### `agrag.ingestion.BAMLExtractor.extract` \{#agrag-ingestion-BAMLExtractor-extract}

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract with an LLM call through the configured ClientRegistry.

**Parameters:**

- **chunk** (<code>[Chunk](common.md#agrag-common-data_models-chunk-Chunk)</code>) – The chunk to read. Only `chunk.text` and `chunk.id` are used.
- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The entity and relation types to extract.

**Returns:**

- <code>[ExtractionResult](common.md#agrag-common-data_models-extraction-ExtractionResult)</code> – The normalized entities and relations found in the chunk.

**Raises:**

- <code>[ExtractorMissingExtraError](#agrag-ingestion-extract-ExtractorMissingExtraError)</code> – The `llm` package extra is not
  installed.
- <code>ValueError</code> – `chunk.id` is `None`.

#### `agrag.ingestion.BAMLExtractor.settings` \{#agrag-ingestion-BAMLExtractor-settings}

```python
settings = settings
```

### `agrag.ingestion.CommunityDetectionReport` \{#agrag-ingestion-CommunityDetectionReport}

Bases: <code>BaseModel</code>

Report from Graph.detect_communities().

**Attributes:**

- [**communities**](#agrag-ingestion-CommunityDetectionReport-communities) (<code>list\[[Community](common.md#agrag-common-data_models-community-Community)\]</code>) – The communities this call found, whether applied or not.
- [**applied**](#agrag-ingestion-CommunityDetectionReport-applied) (<code>bool</code>) – Whether the communities were written.
- [**failures**](#agrag-ingestion-CommunityDetectionReport-failures) (<code>list\[[StageFailure](common.md#agrag-common-data_models-stage_failure-StageFailure)\]</code>) – Failures generating an applied community's LLM report or
  embedding its report text. A failed community still gets
  written, with a heuristic report or a missing embedding in
  place of the failed step. Always empty when apply is False.

#### `agrag.ingestion.CommunityDetectionReport.applied` \{#agrag-ingestion-CommunityDetectionReport-applied}

```python
applied: bool = False
```

#### `agrag.ingestion.CommunityDetectionReport.communities` \{#agrag-ingestion-CommunityDetectionReport-communities}

```python
communities: list[Community] = Field(default_factory=list)
```

#### `agrag.ingestion.CommunityDetectionReport.failures` \{#agrag-ingestion-CommunityDetectionReport-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

### `agrag.ingestion.ConsolidationReport` \{#agrag-ingestion-ConsolidationReport}

Bases: <code>BaseModel</code>

Report from Graph.consolidate().

**Attributes:**

- [**would_match**](#agrag-ingestion-ConsolidationReport-would_match) (<code>list\[[MatchDecision](#agrag-ingestion-resolved_entities-MatchDecision)\]</code>) – Confirmed non-exact matches found, whether applied or not.
- [**applied**](#agrag-ingestion-ConsolidationReport-applied) (<code>bool</code>) – Whether the matches were applied.
- [**failures**](#agrag-ingestion-ConsolidationReport-failures) (<code>list\[[StageFailure](common.md#agrag-common-data_models-stage_failure-StageFailure)\]</code>) – Failures writing a match graph or rebuilding resolved entities.
  Always empty when apply is False.
- [**ambiguous_count**](#agrag-ingestion-ConsolidationReport-ambiguous_count) (<code>int</code>) – LLM verdicts that came back uncertain. These
  pairs never merge.

#### `agrag.ingestion.ConsolidationReport.ambiguous_count` \{#agrag-ingestion-ConsolidationReport-ambiguous_count}

```python
ambiguous_count: int = 0
```

#### `agrag.ingestion.ConsolidationReport.applied` \{#agrag-ingestion-ConsolidationReport-applied}

```python
applied: bool = False
```

#### `agrag.ingestion.ConsolidationReport.failures` \{#agrag-ingestion-ConsolidationReport-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

#### `agrag.ingestion.ConsolidationReport.would_match` \{#agrag-ingestion-ConsolidationReport-would_match}

```python
would_match: list[MatchDecision] = Field(default_factory=list)
```

### `agrag.ingestion.EscalatingExtractor` \{#agrag-ingestion-EscalatingExtractor}

```python
EscalatingExtractor(primary:Extractor, escalate_to:Extractor, *, min_confidence:float = 0.5, min_chunk_words:int = 8, tracer:Tracer | None = None) -> None
```

Bases: <code>[Extractor](#agrag-ingestion-extract-Extractor)</code>

Runs a cheap extractor on every chunk and a stronger one on weak results.

The primary extractor runs first. A chunk escalates when the primary finds no
entities in a chunk of at least `min_chunk_words` words, or when the mean
entity confidence is below `min_confidence`. An escalated chunk gets the
`escalate_to` result alone; the two results are never combined. A common
pairing is `GlinerExtractor` as primary and `BAMLExtractor` as fallback.

**Parameters:**

- **primary** (<code>[Extractor](#agrag-ingestion-extract-Extractor)</code>) – Extractor that runs on every chunk.
- **escalate_to** (<code>[Extractor](#agrag-ingestion-extract-Extractor)</code>) – Extractor that replaces the primary result when escalation
  triggers.
- **min_confidence** (<code>float</code>) – Escalate when the primary's mean reported confidence is
  below this value.
- **min_chunk_words** (<code>int</code>) – Treat an empty primary result as weak only when the
  chunk has at least this many words.
- **tracer** (<code>Tracer | None</code>) – Opens the `agrag.extraction.escalating` span. `None` opens
  no recorded span.

**Functions:**

- [**extract**](#agrag-ingestion-EscalatingExtractor-extract) – Extract with the primary extractor, escalating when it's weak.

**Attributes:**

- [**escalate_to**](#agrag-ingestion-EscalatingExtractor-escalate_to) –
- [**min_chunk_words**](#agrag-ingestion-EscalatingExtractor-min_chunk_words) –
- [**min_confidence**](#agrag-ingestion-EscalatingExtractor-min_confidence) –
- [**primary**](#agrag-ingestion-EscalatingExtractor-primary) –

#### `agrag.ingestion.EscalatingExtractor.escalate_to` \{#agrag-ingestion-EscalatingExtractor-escalate_to}

```python
escalate_to = escalate_to
```

#### `agrag.ingestion.EscalatingExtractor.extract` \{#agrag-ingestion-EscalatingExtractor-extract}

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract with the primary extractor, escalating when it's weak.

**Parameters:**

- **chunk** (<code>[Chunk](common.md#agrag-common-data_models-chunk-Chunk)</code>) – The chunk to read.
- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The entity and relation types to extract.

**Returns:**

- <code>[ExtractionResult](common.md#agrag-common-data_models-extraction-ExtractionResult)</code> – The primary result, or the escalation result when escalation triggers.

#### `agrag.ingestion.EscalatingExtractor.min_chunk_words` \{#agrag-ingestion-EscalatingExtractor-min_chunk_words}

```python
min_chunk_words = min_chunk_words
```

#### `agrag.ingestion.EscalatingExtractor.min_confidence` \{#agrag-ingestion-EscalatingExtractor-min_confidence}

```python
min_confidence = min_confidence
```

#### `agrag.ingestion.EscalatingExtractor.primary` \{#agrag-ingestion-EscalatingExtractor-primary}

```python
primary = primary
```

### `agrag.ingestion.ExtractionLLMSettings` \{#agrag-ingestion-ExtractionLLMSettings}

Bases: <code>BaseSettings</code>

Env-backed LLM client config for the extraction role.

**Attributes:**

- [**clients**](#agrag-ingestion-ExtractionLLMSettings-clients) (<code>list\[LLMClientConfig\]</code>) – The LLM client(s) to use. One element for a single provider;
  more than one composed per `strategy`.
- [**strategy**](#agrag-ingestion-ExtractionLLMSettings-strategy) (<code>Literal['single', 'fallback', 'round_robin']</code>) – How to compose multiple clients. Ignored with one client.
- [**retry**](#agrag-ingestion-ExtractionLLMSettings-retry) (<code>RetryConfig</code>) – Retry settings applied to the extraction LLM call.

Env prefix: `EXTRACTION_LLM_`.

**Functions:**

- [**from_openai_compatible_env**](#agrag-ingestion-ExtractionLLMSettings-from_openai_compatible_env) – Build settings from a generic OpenAI-compatible endpoint.

#### `agrag.ingestion.ExtractionLLMSettings.clients` \{#agrag-ingestion-ExtractionLLMSettings-clients}

```python
clients: list[LLMClientConfig]
```

#### `agrag.ingestion.ExtractionLLMSettings.from_openai_compatible_env` \{#agrag-ingestion-ExtractionLLMSettings-from_openai_compatible_env}

```python
from_openai_compatible_env() -> ExtractionLLMSettings
```

Build settings from a generic OpenAI-compatible endpoint.

Reads `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL_ID` from the
environment or `.env`, so the model name is never hardcoded. Raises
`RuntimeError` when the required variables are not all set.

**Returns:**

- <code>[ExtractionLLMSettings](#agrag-ingestion-extract-ExtractionLLMSettings)</code> – Settings pointing at one `openai-generic` client.

#### `agrag.ingestion.ExtractionLLMSettings.model_config` \{#agrag-ingestion-ExtractionLLMSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='EXTRACTION_LLM_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

#### `agrag.ingestion.ExtractionLLMSettings.retry` \{#agrag-ingestion-ExtractionLLMSettings-retry}

```python
retry: RetryConfig = Field(default_factory=RetryConfig)
```

#### `agrag.ingestion.ExtractionLLMSettings.strategy` \{#agrag-ingestion-ExtractionLLMSettings-strategy}

```python
strategy: Literal['single', 'fallback', 'round_robin'] = 'single'
```

### `agrag.ingestion.Extractor` \{#agrag-ingestion-Extractor}

Bases: <code>ABC</code>

Reads one chunk and returns the entities and relations it contains.

<details class="note" open markdown="1">
<summary>Note</summary>

Subclass this class to provide custom extraction. `Graph` awaits
`extract` once for each chunk. The built-in extractors are
`GlinerExtractor` (a local model), `BAMLExtractor` (an LLM call),
and `EscalatingExtractor` (a cheap extractor first, a stronger one
when the result is weak).

</details>

**Functions:**

- [**extract**](#agrag-ingestion-Extractor-extract) – Extract entities and relations from one chunk.

#### `agrag.ingestion.Extractor.extract` \{#agrag-ingestion-Extractor-extract}

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract entities and relations from one chunk.

**Parameters:**

- **chunk** (<code>[Chunk](common.md#agrag-common-data_models-chunk-Chunk)</code>) – The chunk to read. Only `chunk.text` and `chunk.id` are used.
- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The entity/relation types to extract. Every returned entity's
  `label` and relation's `label` must be declared in this schema.

**Returns:**

- <code>[ExtractionResult](common.md#agrag-common-data_models-extraction-ExtractionResult)</code> – The entities and relations this call found, in extraction order.

### `agrag.ingestion.ExtractorMissingExtraError` \{#agrag-ingestion-ExtractorMissingExtraError}

```python
ExtractorMissingExtraError(component:str, extra:str) -> None
```

Bases: <code>[IngestionError](loaders.md#agrag-loaders-corpus-errors-IngestionError)</code>

An Extractor needs a package extra that is not installed.

**Attributes:**

- [**component**](#agrag-ingestion-ExtractorMissingExtraError-component) – The class name that needs the extra.
- [**extra**](#agrag-ingestion-ExtractorMissingExtraError-extra) – The package extra to install.

#### `agrag.ingestion.ExtractorMissingExtraError.component` \{#agrag-ingestion-ExtractorMissingExtraError-component}

```python
component = component
```

#### `agrag.ingestion.ExtractorMissingExtraError.extra` \{#agrag-ingestion-ExtractorMissingExtraError-extra}

```python
extra = extra
```

### `agrag.ingestion.GlinerExtractor` \{#agrag-ingestion-GlinerExtractor}

```python
GlinerExtractor(*, model_name:str = 'fastino/gliner2.5-small-v1', model:object | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Extractor](#agrag-ingestion-extract-Extractor)</code>

Extracts entities and relations with a local GLiNER2.5 model.

The model runs in this process, so extraction needs no LLM key. It loads on
first use and one load serves concurrent calls. The first load downloads the
weights from Hugging Face unless `model` is passed. GLiNER reports entity
spans and types, so extracted entities carry no property values. Needs the
`extract` extra.

**Parameters:**

- **model_name** (<code>str</code>) – Checkpoint to load when `model` is not provided.
- **model** (<code>object | None</code>) – An already-built GLiNER2.5 model.
- **tracer** (<code>Tracer | None</code>) – Opens `agrag.extraction.gliner` and
  `agrag.extraction.model_load` spans. `None` opens no recorded
  span.

**Functions:**

- [**extract**](#agrag-ingestion-GlinerExtractor-extract) – Extract with the local GLiNER2.5 model.

**Attributes:**

- [**model_name**](#agrag-ingestion-GlinerExtractor-model_name) –

#### `agrag.ingestion.GlinerExtractor.extract` \{#agrag-ingestion-GlinerExtractor-extract}

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract with the local GLiNER2.5 model.

**Parameters:**

- **chunk** (<code>[Chunk](common.md#agrag-common-data_models-chunk-Chunk)</code>) – The chunk to read. Only `chunk.text` and `chunk.id` are used.
- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The entity and relation types to extract.

**Returns:**

- <code>[ExtractionResult](common.md#agrag-common-data_models-extraction-ExtractionResult)</code> – The normalized entities and relations found in the chunk.

**Raises:**

- <code>[ExtractorMissingExtraError](#agrag-ingestion-extract-ExtractorMissingExtraError)</code> – The `extract` package extra is not
  installed.
- <code>ValueError</code> – `chunk.id` is `None`.

#### `agrag.ingestion.GlinerExtractor.model_name` \{#agrag-ingestion-GlinerExtractor-model_name}

```python
model_name = model_name
```

### `agrag.ingestion.Graph` \{#agrag-ingestion-Graph}

```python
Graph(*, schema:GraphSchema, graph_store:GraphStore, embedder:Embedder, extractor:Extractor, tracer:Tracer | None = None, vector_store:VectorStore | None = None, retrieval_settings:RetrievalSettings | None = None, cutover_settings:CutoverJobSettings | None = None, chunking:Chunking = DEFAULT_CHUNKING, embed_heading_path:bool = True, max_llm_pairs:int = MAX_LLM_PAIRS) -> None
```

A knowledge graph that a caller can open and add content to.

When an optional VectorStore is configured, every embedding this
graph writes to graph_store is also upserted there, so SearchEngine's
VectorStore path finds the same vectors the GraphStore-native path
does. Collections follow RetrievalSettings' names and are provisioned
by `open()` when missing.

**Functions:**

- [**add**](#agrag-ingestion-Graph-add) – Add content to the graph.
- [**consolidate**](#agrag-ingestion-Graph-consolidate) – Run non-destructive resolution against every persisted raw entity.
- [**deactivate_match**](#agrag-ingestion-Graph-deactivate_match) – Deactivate a semantic match and synchronize replacement retrieval vectors.
- [**delete_document**](#agrag-ingestion-Graph-delete_document) – Soft-delete a document by closing its current PART_OF edges.
- [**detect_communities**](#agrag-ingestion-Graph-detect_communities) – Detect entity communities via hierarchical Leiden.
- [**open**](#agrag-ingestion-Graph-open) – Open a graph, connecting and fully provisioning graph_store.
- [**reevaluate**](#agrag-ingestion-Graph-reevaluate) – Reevaluate matches among the given entities, adding and removing edges.
- [**update**](#agrag-ingestion-Graph-update) – Replace one document version, closing its former PART_OF edges.

**Attributes:**

- [**chunking**](#agrag-ingestion-Graph-chunking) (<code>[Chunking](chunking.md#agrag-chunking-Chunking)</code>) – The rules that pick a chunker for each document.

**Parameters:**

- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The entity/relation types this graph validates every
  extraction against.
- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Where entities, relations, chunks, and MENTIONED_IN
  edges are written.
- **embedder** (<code>[Embedder](embedding.md#agrag-embedding-base-Embedder)</code>) – Populates entity embeddings for native vector search.
- **extractor** (<code>[Extractor](#agrag-ingestion-extract-Extractor)</code>) – Runs against each chunk.
- **tracer** (<code>Tracer | None</code>) – A tracer to record spans for every step. Pass None for none.
- **vector_store** (<code>[VectorStore](vectordb.md#agrag-vectordb-base-VectorStore) | None</code>) – Optional second write target for embeddings. When
  set, every embedding the pipeline writes to graph_store is
  also upserted here, so SearchEngine's VectorStore path finds
  the same vectors the GraphStore-native path does. Also gets
  old community vectors removed on each
  detect_communities(apply=True) cycle.
- **retrieval_settings** (<code>[RetrievalSettings](retrieval.md#agrag-retrieval-settings-RetrievalSettings) | None</code>) – Collection names for the VectorStore writes.
  None uses RetrievalSettings defaults. Ignored when
  vector_store is None.
- **cutover_settings** (<code>[CutoverJobSettings](#agrag-ingestion-settings-CutoverJobSettings) | None</code>) – Lease configuration for the Cutover Jobs
  add/update/delete_document run through. None uses
  CutoverJobSettings defaults.
- **chunking** (<code>[Chunking](chunking.md#agrag-chunking-Chunking)</code>) – The rules that pick a chunker for each document. The
  default is `DEFAULT_CHUNKING`.
- **embed_heading_path** (<code>bool</code>) – Whether chunk embeddings include the chunk's
  heading path above its text. The stored text does not change.
  Existing embeddings stay until a document is re-chunked with
  `update()`.
- **max_llm_pairs** (<code>int</code>) – The most ambiguous entity pairs that resolution sends
  to the LLM for each label. A lower value bounds the number of
  verification calls and leaves more pairs undecided.

#### `agrag.ingestion.Graph.add` \{#agrag-ingestion-Graph-add}

```python
add(source:SourcesType | None = None, *, text:str | None = None, documents:Sequence[Document] | None = None, loader:Loader | None = None, error_policy:ErrorPolicy = ErrorPolicy.RAISE, on_progress:Callable[[AddResult], None] | None = None, return_chunks:bool = False, read_options:ReadOptions | None = None) -> AddResult
```

Add content to the graph.

Give exactly one of `source`, `text`, and `documents`.

**Parameters:**

- **source** (<code>[SourcesType](#agrag-ingestion-graph-SourcesType) | None</code>) – A file path, a directory, a glob, or a list of these.
- **text** (<code>str | None</code>) – Raw text to add as one document.
- **documents** (<code>Sequence\[[Document](common.md#agrag-common-data_models-document-Document)\] | None</code>) – Already-built documents to add directly.
- **loader** (<code>[Loader](loaders.md#agrag-loaders-corpus-base-Loader) | None</code>) – A loader to use instead of the registry default. Requires a
  single-file `source`; a directory, glob, or list of sources raises an
  error.
- **error_policy** (<code>[ErrorPolicy](loaders.md#agrag-loaders-corpus-types-ErrorPolicy)</code>) – The action to take on a per-source error.
- **on_progress** (<code>Callable\[\[[AddResult](#agrag-ingestion-reports-AddResult)\], None\] | None</code>) – A callback the call runs after each batch and once more
  at the end with the fully-populated result.
- **return_chunks** (<code>bool</code>) – Whether to include the produced chunks in the
  returned AddResult. False by default to avoid holding full text
  for a large corpus when not needed.
- **read_options** (<code>[ReadOptions](loaders.md#agrag-loaders-corpus-types-ReadOptions) | None</code>) – How loaders read sources, including the normalization of
  decoded text. None uses `ReadOptions()` defaults.

**Returns:**

- <code>[AddResult](#agrag-ingestion-reports-AddResult)</code> – A summary of what was added per pipeline stage. Resolution runs
- **automatically** (<code>[AddResult](#agrag-ingestion-reports-AddResult)</code>) – exact identity plus fuzzy, embedding, and
- <code>[AddResult](#agrag-ingestion-reports-AddResult)</code> – capped LLM zones over one combined mention list, with
- <code>[AddResult](#agrag-ingestion-reports-AddResult)</code> – confirmed matches persisted as MATCHES edges and derived
- <code>[AddResult](#agrag-ingestion-reports-AddResult)</code> – ResolvedEntity nodes. LLM verification calls stay bounded
- <code>[AddResult](#agrag-ingestion-reports-AddResult)</code> – at ceil(L * MAX_LLM_PAIRS / 10) requests for L labels;
- <code>[AddResult](#agrag-ingestion-reports-AddResult)</code> – inspect result.resolution.ambiguous_count for the pairs no
- <code>[AddResult](#agrag-ingestion-reports-AddResult)</code> – tier could decide.

**Raises:**

- <code>ValueError</code> – The call got zero, or more than one, of `source`, `text`,
  and `documents`. Also raised when `loader` is set without
  `source`, or with a source that can match more than one file.
- <code>UnsupportedFormatError</code> – No loader is registered for a source's format.
- <code>MissingExtraError</code> – A loader is registered for a source's format, but its
  package extra is not installed. This error follows `error_policy`
  instead of always stopping the call.
- <code>ValueError</code> – The input contains multiple documents with the same
  `document_key`.

#### `agrag.ingestion.Graph.chunking` \{#agrag-ingestion-Graph-chunking}

```python
chunking: Chunking
```

The rules that pick a chunker for each document.

#### `agrag.ingestion.Graph.consolidate` \{#agrag-ingestion-Graph-consolidate}

```python
consolidate(*, apply:bool = False) -> ConsolidationReport
```

Run non-destructive resolution against every persisted raw entity.

Dry-run by default: produces matches before any node is touched. Pass
apply=True to write MATCHES edges and derived ResolvedEntity nodes.

For each EntityType label in self.\_schema, fetches every persisted
entity with that label, bounds the pairs actually compared with
GraphCandidateSource's ANN-backed persisted_candidate_indices, and
runs the same zone-routed resolution add() uses (exact, fuzzy
fast-path, embedding similarity, capped LLM review) over those
candidate pairs. Confirmed non-exact matches preserve both raw
Entity nodes and their relationships.

LLM verification calls stay bounded: at most
ceil(L * MAX_LLM_PAIRS / 10) requests for L labels. See Graph.add.

**Parameters:**

- **apply** (<code>bool</code>) – Write the confirmed matches and rebuild resolved entities.
  False produces a report only.

**Returns:**

- <code>[ConsolidationReport](#agrag-ingestion-reports-ConsolidationReport)</code> – A report of every confirmed non-exact match, applied or not,
- <code>[ConsolidationReport](#agrag-ingestion-reports-ConsolidationReport)</code> – plus the count of uncertain LLM verdicts.

#### `agrag.ingestion.Graph.deactivate_match` \{#agrag-ingestion-Graph-deactivate_match}

```python
deactivate_match(match_id:UUID) -> list[ResolvedEntity]
```

Deactivate a semantic match and synchronize replacement retrieval vectors.

#### `agrag.ingestion.Graph.delete_document` \{#agrag-ingestion-Graph-delete_document}

```python
delete_document(document_key:str) -> UpdateResult
```

Soft-delete a document by closing its current PART_OF edges.

Currency is read transitively through `PART_OF`: closing the
open edges removes the document from retrieval while its chunks,
the `Document` node, and contributed entities stay in the graph
for provenance. An unknown `document_key` is a no-op. Entities
mentioned only by this document's chunks lose their last evidence
and are pruned with their shrunken clusters. The close and the
prune run as one job's commit and cleanup, so a crash either
leaves the document untouched or completes the deletion.

**Parameters:**

- **document_key** (<code>str</code>) – The stable key of the document to delete.

**Returns:**

- <code>[UpdateResult](#agrag-ingestion-reports-UpdateResult)</code> – The deletion summary: `no_op=True` when nothing was stored
- <code>[UpdateResult](#agrag-ingestion-reports-UpdateResult)</code> – under the key, otherwise `chunks_closed` with
- <code>[UpdateResult](#agrag-ingestion-reports-UpdateResult)</code> – `new_content_hash=None` and no `add_result`.

<details class="note" open markdown="1">
<summary>Note</summary>

The close-only degenerate case of `Graph.update()`; both
call into the same shared document-lifecycle helpers. See
`Graph.add()` for the shared ingestion behavior.

</details>

#### `agrag.ingestion.Graph.detect_communities` \{#agrag-ingestion-Graph-detect_communities}

```python
detect_communities(*, apply:bool = False, max_cluster_size:int = 10, resolution:float = 1.0, seed:int | None = 3735928559) -> CommunityDetectionReport
```

Detect entity communities via hierarchical Leiden.

Dry-run by default: produces a report of the communities that would be
written before any node is touched. Pass apply=True to write them.

Fetches every live domain relation across the whole graph (not scoped
by entity label the way consolidate() is -- community structure spans
entity types), builds a weighted edge list, and runs hierarchical
Leiden off the event loop. Every prior run's Community nodes and
MEMBER_OF edges are deleted before the new ones are written when
apply=True: this is a full recompute, not an incremental update,
so there is no notion of merging this run's output with a
previous one's.

**Parameters:**

- **apply** (<code>bool</code>) – Write the computed communities. False produces a report only.
- **max_cluster_size** (<code>int</code>) – Forwarded to compute_communities.
- **resolution** (<code>float</code>) – Forwarded to compute_communities.
- **seed** (<code>int | None</code>) – Forwarded to compute_communities.

**Returns:**

- <code>[CommunityDetectionReport](#agrag-ingestion-reports-CommunityDetectionReport)</code> – A report of every community this call found, applied or not.

**Raises:**

- <code>[CommunityDetectionMissingExtraError](#agrag-ingestion-community-CommunityDetectionMissingExtraError)</code> –
  graspologic-native is not installed.

#### `agrag.ingestion.Graph.open` \{#agrag-ingestion-Graph-open}

```python
open(*, schema:GraphSchema, graph_store:GraphStore, embedder:Embedder, extractor:Extractor, tracer:Tracer | None = None, vector_store:VectorStore | None = None, retrieval_settings:RetrievalSettings | None = None, cutover_settings:CutoverJobSettings | None = None, chunking:Chunking = DEFAULT_CHUNKING, embed_heading_path:bool = True, max_llm_pairs:int = MAX_LLM_PAIRS) -> Graph
```

Open a graph, connecting and fully provisioning graph_store.

Provisioning order: connect, then register every label/relation type
this graph will ever write (schema's own labels/types plus the fixed
system names CHUNK_LABEL/SYSTEM_RELATION_TYPES), then
setup_constraints(), then setup_indexes(), then vector indexes for
every schema entity label — so a brand-new database is fully ready,
including the merge_key uniqueness constraints the global exact-match
tier relies on and the embedding vector indexes native search needs,
before this call returns. When vector_store is set, the entity, chunk,
and community collections are provisioned there too (created when
missing) so the dual writes never hit an absent collection.

**Parameters:**

- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The entity/relation types this graph validates every
  extraction against.
- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Where entities, relations, chunks, and MENTIONED_IN
  edges are written.
- **embedder** (<code>[Embedder](embedding.md#agrag-embedding-base-Embedder)</code>) – Populates entity embeddings for native vector search.
- **extractor** (<code>[Extractor](#agrag-ingestion-extract-Extractor)</code>) – Runs against each chunk.
- **tracer** (<code>Tracer | None</code>) – A tracer to record spans for every step. Pass None for none.
- **vector_store** (<code>[VectorStore](vectordb.md#agrag-vectordb-base-VectorStore) | None</code>) – Optional second write target for embeddings; see
  __init__.
- **retrieval_settings** (<code>[RetrievalSettings](retrieval.md#agrag-retrieval-settings-RetrievalSettings) | None</code>) – Collection names for the VectorStore writes.
  None uses RetrievalSettings defaults.
- **cutover_settings** (<code>[CutoverJobSettings](#agrag-ingestion-settings-CutoverJobSettings) | None</code>) – Lease configuration for the Cutover Jobs
  add/update/delete_document run through. None uses
  CutoverJobSettings defaults.
- **chunking** (<code>[Chunking](chunking.md#agrag-chunking-Chunking)</code>) – The rules that pick a chunker for each document; see
  __init__.
- **embed_heading_path** (<code>bool</code>) – Whether chunk embeddings include the heading path;
  see __init__.
- **max_llm_pairs** (<code>int</code>) – The most ambiguous entity pairs sent to the LLM for each
  label during resolution; see __init__.

**Returns:**

- <code>[Graph](#agrag-ingestion-graph-Graph)</code> – A graph connected to graph_store and ready to accept add() calls.

**Raises:**

- <code>EmbeddingDimensionMismatchError</code> – A vector index in graph_store
  already exists with a different dimension than the embedder
  produces.
- <code>CollectionDimensionMismatchError</code> – A vector_store collection
  already exists with a different dimension than the embedder
  produces.
- <code>Exception</code> – Whatever connect(), registration, constraint/index
  setup, or vector-index provisioning raises. graph_store is
  closed first, so a failed open() never leaks a connection.

#### `agrag.ingestion.Graph.reevaluate` \{#agrag-ingestion-Graph-reevaluate}

```python
reevaluate(entity_ids:list[UUID]) -> ReevaluationReport
```

Reevaluate matches among the given entities, adding and removing edges.

Fetches exactly the supplied entities, compares same-label pairs
only among this set through one zone-routed Resolver pass, writes
confirmed matches that lack an active edge, and deactivates active
edges among the set the resolver did not confirm. Exact-text pairs
never gain or lose edges. Nothing outside the input set is compared
or touched, and nothing calls this automatically.

LLM verification calls stay bounded at ceil(L * MAX_LLM_PAIRS / 10)
requests for L labels, as in Graph.add.

**Parameters:**

- **entity_ids** (<code>list\[UUID\]</code>) – The persisted entities to reevaluate, deduped with
  input order preserved.

**Returns:**

- <code>[ReevaluationReport](#agrag-ingestion-reports-ReevaluationReport)</code> – Which entities were reevaluated, which matches were added,
- <code>[ReevaluationReport](#agrag-ingestion-reports-ReevaluationReport)</code> – which match edges were deactivated, and how many inputs had no
- <code>[ReevaluationReport](#agrag-ingestion-reports-ReevaluationReport)</code> – incident added or removed edge.

**Raises:**

- <code>ValueError</code> – An id has no live persisted entity.

#### `agrag.ingestion.Graph.update` \{#agrag-ingestion-Graph-update}

```python
update(document_key:str, *, text:str | None = None, source:SourcesType | None = None, loader:Loader | None = None, error_policy:ErrorPolicy = ErrorPolicy.RAISE, read_options:ReadOptions | None = None) -> UpdateResult
```

Replace one document version, closing its former PART_OF edges.

Looks up the persisted `Document` node by `document_key`. An
unchanged content hash is a no-op returning before any chunking,
extraction, or writes, unless the chunker that this graph's rules pick
for the document differs from the one that made its current chunks. A
chunker with new settings re-chunks the document as a content change
does. Chunks written before chunkers were recorded count as unchanged.
Otherwise the fresh content ingests under a Cutover Job holding this
document's lease, and the commit flips the job, closes the document's
open `PART_OF` edges, and clears every pending tag in one
transaction — so a crash either leaves
the old version untouched or completes the replacement including
cleanup. Entities that lose their last evidence are pruned after
the commit, so replacement mentions count as evidence. A source
must resolve to exactly one document.

**Parameters:**

- **document_key** (<code>str</code>) – The stable key of the document to replace.
- **text** (<code>str | None</code>) – Replacement text, exactly one of `text`/`source`.
- **source** (<code>[SourcesType](#agrag-ingestion-graph-SourcesType) | None</code>) – A single-file source, glob, or path list resolving to
  exactly one document.
- **loader** (<code>[Loader](loaders.md#agrag-loaders-corpus-base-Loader) | None</code>) – A loader override for a single-file `source`.
- **error_policy** (<code>[ErrorPolicy](loaders.md#agrag-loaders-corpus-types-ErrorPolicy)</code>) – RAISE propagates a stage failure; any other
  policy records it and continues.
- **read_options** (<code>[ReadOptions](loaders.md#agrag-loaders-corpus-types-ReadOptions) | None</code>) – How loaders read the replacement, including the
  normalization of its text. None uses `ReadOptions()` defaults.

**Returns:**

- <code>[UpdateResult](#agrag-ingestion-reports-UpdateResult)</code> – The update summary. A no-op reports `no_op=True` with no
- <code>[UpdateResult](#agrag-ingestion-reports-UpdateResult)</code> – `add_result`; a change reports `chunks_closed` plus the
- <code>[UpdateResult](#agrag-ingestion-reports-UpdateResult)</code> – fresh ingestion's `add_result`; an unknown `document_key`
- <code>[UpdateResult](#agrag-ingestion-reports-UpdateResult)</code> – ingests fresh with `previous_content_hash=None` and
- <code>[UpdateResult](#agrag-ingestion-reports-UpdateResult)</code> – `chunks_closed=0`.

**Raises:**

- <code>ValueError</code> – Both or neither of `text` and `source` are given, a loader
  override targets multiple sources, or a source resolves to any number
  of documents other than one.

<details class="note" open markdown="1">
<summary>Note</summary>

The fresh-content path shares `ingest_chunks()` with
`Graph.add()`; both callers observe the same pipeline behavior
for the same input.

</details>

### `agrag.ingestion.ReevaluationReport` \{#agrag-ingestion-ReevaluationReport}

Bases: <code>BaseModel</code>

Report from Graph.reevaluate().

**Attributes:**

- [**entities_reevaluated**](#agrag-ingestion-ReevaluationReport-entities_reevaluated) (<code>list\[UUID\]</code>) – Input entity ids reevaluated, deduped with
  input order preserved.
- [**matches_added**](#agrag-ingestion-ReevaluationReport-matches_added) (<code>list\[[MatchDecision](#agrag-ingestion-resolved_entities-MatchDecision)\]</code>) – Confirmed matches with no active edge, now written.
- [**matches_removed**](#agrag-ingestion-ReevaluationReport-matches_removed) (<code>list\[UUID\]</code>) – Ids of active match edges the resolver did not
  confirm, now deactivated.
- [**unchanged_count**](#agrag-ingestion-ReevaluationReport-unchanged_count) (<code>int</code>) – Input entities with no incident added or removed
  edge.

#### `agrag.ingestion.ReevaluationReport.entities_reevaluated` \{#agrag-ingestion-ReevaluationReport-entities_reevaluated}

```python
entities_reevaluated: list[UUID] = Field(default_factory=list)
```

#### `agrag.ingestion.ReevaluationReport.matches_added` \{#agrag-ingestion-ReevaluationReport-matches_added}

```python
matches_added: list[MatchDecision] = Field(default_factory=list)
```

#### `agrag.ingestion.ReevaluationReport.matches_removed` \{#agrag-ingestion-ReevaluationReport-matches_removed}

```python
matches_removed: list[UUID] = Field(default_factory=list)
```

#### `agrag.ingestion.ReevaluationReport.unchanged_count` \{#agrag-ingestion-ReevaluationReport-unchanged_count}

```python
unchanged_count: int = 0
```

### `agrag.ingestion.UpdateResult` \{#agrag-ingestion-UpdateResult}

Bases: <code>BaseModel</code>

Summary of an update or soft deletion.

**Attributes:**

- [**document_key**](#agrag-ingestion-UpdateResult-document_key) (<code>str</code>) – Stable identity used for the document node.
- [**no_op**](#agrag-ingestion-UpdateResult-no_op) (<code>bool</code>) – Whether no graph changes were needed.
- [**previous_content_hash**](#agrag-ingestion-UpdateResult-previous_content_hash) (<code>str | None</code>) – Hash stored before the operation, if present.
- [**new_content_hash**](#agrag-ingestion-UpdateResult-new_content_hash) (<code>str | None</code>) – Hash written by an update, or `None` on deletion.
- [**chunks_closed**](#agrag-ingestion-UpdateResult-chunks_closed) (<code>int</code>) – Number of open PART_OF edges closed.
- [**add_result**](#agrag-ingestion-UpdateResult-add_result) (<code>[AddResult](#agrag-ingestion-reports-add_result-AddResult) | None</code>) – Ingestion details for changed content, if any.

#### `agrag.ingestion.UpdateResult.add_result` \{#agrag-ingestion-UpdateResult-add_result}

```python
add_result: AddResult | None = None
```

#### `agrag.ingestion.UpdateResult.chunks_closed` \{#agrag-ingestion-UpdateResult-chunks_closed}

```python
chunks_closed: int = 0
```

#### `agrag.ingestion.UpdateResult.document_key` \{#agrag-ingestion-UpdateResult-document_key}

```python
document_key: str
```

#### `agrag.ingestion.UpdateResult.new_content_hash` \{#agrag-ingestion-UpdateResult-new_content_hash}

```python
new_content_hash: str | None = None
```

#### `agrag.ingestion.UpdateResult.no_op` \{#agrag-ingestion-UpdateResult-no_op}

```python
no_op: bool
```

#### `agrag.ingestion.UpdateResult.previous_content_hash` \{#agrag-ingestion-UpdateResult-previous_content_hash}

```python
previous_content_hash: str | None = None
```

### `agrag.ingestion.community` \{#agrag-ingestion-community}

Community detection: hierarchical Leiden over the entity graph.

**Classes:**

- [**CommunityDetectionMissingExtraError**](#agrag-ingestion-community-CommunityDetectionMissingExtraError) – Raised when graspologic-native is not installed.

**Functions:**

- [**compute_communities**](#agrag-ingestion-community-compute_communities) – Run hierarchical Leiden and return level-0 communities.
- [**delete_all_communities**](#agrag-ingestion-community-delete_all_communities) – Delete every Community node and its edges, in batches.
- [**embed_communities**](#agrag-ingestion-community-embed_communities) – Compute each community's embedding from its report text, in place.
- [**fetch_relation_edges**](#agrag-ingestion-community-fetch_relation_edges) – Return every live domain relation as a weighted edge tuple.
- [**generate_community_reports**](#agrag-ingestion-community-generate_community_reports) – Generate a report for each community, in place.
- [**required_member_ids**](#agrag-ingestion-community-required_member_ids) – Return the member ids generate_community_reports will actually read.

**Attributes:**

- [**WeightedEdge**](#agrag-ingestion-community-WeightedEdge) – One domain relation as (source_id, target_id, weight, relation_type).
- [**logger**](#agrag-ingestion-community-logger) –

#### `agrag.ingestion.community.CommunityDetectionMissingExtraError` \{#agrag-ingestion-community-CommunityDetectionMissingExtraError}

```python
CommunityDetectionMissingExtraError(extra:str = 'community') -> None
```

Bases: <code>Exception</code>

Raised when graspologic-native is not installed.

#### `agrag.ingestion.community.WeightedEdge` \{#agrag-ingestion-community-WeightedEdge}

```python
WeightedEdge = tuple[str, str, float, str]
```

One domain relation as (source_id, target_id, weight, relation_type).

#### `agrag.ingestion.community.compute_communities` \{#agrag-ingestion-community-compute_communities}

```python
compute_communities(edges:list[WeightedEdge], *, max_cluster_size:int = 10, resolution:float = 1.0, seed:int | None = 3735928559) -> list[Community]
```

Run hierarchical Leiden and return level-0 communities.

CPU-bound and synchronous; callers on the event loop should run this via
asyncio.to_thread (see Graph.\_chunk_documents for the same pattern with
chunking). Only level 0 is kept -- higher levels are computed for
max_cluster_size capping but never persisted.

After clustering, one extra pass over the same edge list computes a
structural-importance signal, entirely from data already in memory --
no new dependency (graspologic exposes no general centrality function;
see the follow-up research this refinement is based on), no new query:

- Each community's internal_weight (total weight of edges where both
  endpoints are its members) -- signal for which communities get a
  real LLM report instead of a heuristic one.
- Each member's local weight (weight of its own internal edges) --
  used to order member_ids highest-first, so the "most representative"
  members lead the list for both a large qualifying community's
  (token-budget-truncated) LLM prompt and a heuristic report's
  few-name summary.

**Parameters:**

- **edges** (<code>list\[[WeightedEdge](#agrag-ingestion-community-WeightedEdge)\]</code>) – The weighted edge list from fetch_relation_edges, as
  (source_id, target_id, weight, relation_type) tuples.
- **max_cluster_size** (<code>int</code>) – The size ceiling a cluster is split past, at every
  level.
- **resolution** (<code>float</code>) – Leiden's resolution parameter.
- **seed** (<code>int | None</code>) – Random seed for reproducibility. None uses the native
  default.

**Returns:**

- <code>list\[[Community](common.md#agrag-common-data_models-community-Community)\]</code> – One Community per level-0 cluster with two or more members, with
- <code>list\[[Community](common.md#agrag-common-data_models-community-Community)\]</code> – member_ids ordered by local weight descending and internal_weight
- <code>list\[[Community](common.md#agrag-common-data_models-community-Community)\]</code> – set. Reports (title/summary/rating/findings) are left empty; report
- <code>list\[[Community](common.md#agrag-common-data_models-community-Community)\]</code> – generation fills them.

**Raises:**

- <code>[CommunityDetectionMissingExtraError](#agrag-ingestion-community-CommunityDetectionMissingExtraError)</code> – graspologic-native is not
  installed.

#### `agrag.ingestion.community.delete_all_communities` \{#agrag-ingestion-community-delete_all_communities}

```python
delete_all_communities(graph_store:GraphStore | GraphStoreTransaction, *, batch_size:int = _DEFAULT_DELETE_BATCH_SIZE) -> None
```

Delete every Community node and its edges, in batches.

Repeats the bounded delete until a batch reports fewer than
batch_size rows deleted.

**Parameters:**

- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore) | [GraphStoreTransaction](graphdb.md#agrag-graphdb-base-GraphStoreTransaction)</code>) – Where the delete runs. Accepts either a
  `GraphStore` or a `GraphStoreTransaction` handle so a
  caller inside `store.transaction()` can delete and rewrite
  communities atomically.
- **batch_size** (<code>int</code>) – Community nodes deleted per statement.

#### `agrag.ingestion.community.embed_communities` \{#agrag-ingestion-community-embed_communities}

```python
embed_communities(communities:list[Community], *, embedder:Embedder, batch_size:int = _DEFAULT_EMBED_BATCH_SIZE, max_concurrency:int = 4, tracer:Tracer | None = None) -> list[StageFailure]
```

Compute each community's embedding from its report text, in place.

Called after generate_community_reports and before to_node_record(), so
the vector is already present on the very first (and only) write a
replace cycle makes.

Embedder.embed's contract makes no chunking guarantee (see
agrag/embedding/base.py), so at 1M+ entity scale, where a full recompute
can produce 100,000+ communities, this batches the embed() calls itself
rather than passing every community's text in one call.

A batch embed() failure does not block other batches: it is recorded as
one StageFailure per community in that batch, matching the
failure-tolerance shape generate_community_reports already uses. Those
communities keep embedding=None and still get written by
Community.to_node_record(), which omits the embedding property when it
is None, rather than being dropped from the graph.

**Parameters:**

- **communities** (<code>list\[[Community](common.md#agrag-common-data_models-community-Community)\]</code>) – The communities to embed, mutated in place.
- **embedder** (<code>[Embedder](embedding.md#agrag-embedding-base-Embedder)</code>) – Computes one vector per community's embedding_text.
- **batch_size** (<code>int</code>) – Communities embedded per embed() call.
- **max_concurrency** (<code>int</code>) – Max concurrent embed calls.
- **tracer** (<code>Tracer | None</code>) – Opens one span per batch.

**Returns:**

- <code>list\[[StageFailure](common.md#agrag-common-data_models-stage_failure-StageFailure)\]</code> – One StageFailure per community whose batch embed() call failed.

#### `agrag.ingestion.community.fetch_relation_edges` \{#agrag-ingestion-community-fetch_relation_edges}

```python
fetch_relation_edges(graph_store:GraphStore, *, page_size:int = 5000, use_cursor:bool = True) -> list[WeightedEdge]
```

Return every live domain relation as a weighted edge tuple.

Weight is len(source_chunk_ids) (attestation count). A relation with
no attested chunks contributes weight 0.0, so an unsupported edge
cannot inflate clustering or a community's report importance. Two
entities connected by more than one distinct relation type contribute
one edge tuple per type; graspologic_native sums parallel-edge
weights building its own adjacency.

Supports cursor (keyset) pagination for large graphs where `SKIP`
is expensive, and legacy `SKIP` pagination for callers that need
it.

**Parameters:**

- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Where the relations are read from.
- **page_size** (<code>int</code>) – Rows fetched per page.
- **use_cursor** (<code>bool</code>) – When True uses keyset pagination on `(a.id, b.id, type(r), r.id)`; when False uses `SKIP` pagination.

**Returns:**

- <code>list\[[WeightedEdge](#agrag-ingestion-community-WeightedEdge)\]</code> – Edge tuples as (source_id_str, target_id_str, weight, rel_type).

#### `agrag.ingestion.community.generate_community_reports` \{#agrag-ingestion-community-generate_community_reports}

```python
generate_community_reports(communities:list[Community], entities_by_id:dict[UUID, Entity], *, edges:list[WeightedEdge] | None = None, min_importance_for_llm_report:float = _DEFAULT_MIN_IMPORTANCE_FOR_LLM_REPORT, batch_size:int = _DEFAULT_REPORT_BATCH_SIZE, max_members_per_prompt:int = _DEFAULT_MAX_MEMBERS_PER_PROMPT, max_relations_per_prompt:int = _DEFAULT_MAX_RELATIONS_PER_PROMPT, max_concurrency:int = 4, error_policy:ErrorPolicy = ErrorPolicy.SKIP, tracer:Tracer | None = None) -> list[StageFailure]
```

Generate a report for each community, in place.

Communities at or above min_importance_for_llm_report (internal_weight
-- total weight of edges internal to the community, set by
compute_communities) get a real LLM-generated report, batch_size per
call, bounding total call count at scale. internal_weight, not raw
member count, decides this: a small but
densely-attested community can matter more than a larger sparse one.
Communities below the threshold -- most of a large graph's communities,
which sit near the max_cluster_size floor -- get
\_apply_heuristic_report's deterministic report instead, no LLM call at
all.

A qualifying community's member list is truncated to its top
max_members_per_prompt members (already ordered by local weight
descending) before it enters the batch prompt, protecting the batch
call's token budget from one oversized community without an arbitrary
cut -- the members dropped are the least central ones. When edges is
given, each community's prompt also carries its internal
"source REL_TYPE target" lines (most-attested first, truncated to
max_relations_per_prompt), so the report can state connections the
evidence actually attests; a relation whose endpoint Entity was not
loaded is omitted.

When the `llm` extra (baml-py) is not installed, qualifying
communities fall back to the heuristic report too: with ErrorPolicy
SKIP a warning is logged and the pipeline completes, with RAISE the
ImportError propagates.

A batch call failure does not block other batches: it is recorded as
one StageFailure per community in that batch, each of which then falls
back to the heuristic report, matching the failure-tolerance shape
merge.py's description-summarization step already uses. A batch
response with fewer reports than communities (a malformed or truncated
response) falls back to the heuristic report for whatever is left over,
rather than discarding the reports that did come back.

**Parameters:**

- **communities** (<code>list\[[Community](common.md#agrag-common-data_models-community-Community)\]</code>) – The communities to summarize, mutated in place.
- **entities_by_id** (<code>dict\[UUID, [Entity](common.md#agrag-common-data_models-entity-Entity)\]</code>) – Every entity the reports will read, keyed by id,
  for building each community's member-summary context.
- **edges** (<code>list\[[WeightedEdge](#agrag-ingestion-community-WeightedEdge)\] | None</code>) – The weighted edge list from fetch_relation_edges, used to
  build each community's attested-relation context. None omits
  relation context from the prompts.
- **min_importance_for_llm_report** (<code>float</code>) – The internal_weight floor a
  community must meet to get a real LLM report instead of the
  heuristic one.
- **batch_size** (<code>int</code>) – Communities summarized per LLM call.
- **max_members_per_prompt** (<code>int</code>) – Members per community fed into the LLM
  prompt, highest-centrality first.
- **max_relations_per_prompt** (<code>int</code>) – Attested-relation lines per community
  fed into the LLM prompt, most-attested first.
- **max_concurrency** (<code>int</code>) – Max concurrent SummarizeCommunities calls.
- **error_policy** (<code>[ErrorPolicy](loaders.md#agrag-loaders-corpus-types-ErrorPolicy)</code>) – RAISE propagates a batch call failure or a missing
  `llm` extra; anything else records it or falls back and
  continues.
- **tracer** (<code>Tracer | None</code>) – Opens one span per batch.

**Returns:**

- <code>list\[[StageFailure](common.md#agrag-common-data_models-stage_failure-StageFailure)\]</code> – One StageFailure per community whose batch call failed.

#### `agrag.ingestion.community.logger` \{#agrag-ingestion-community-logger}

```python
logger = logging.getLogger(__name__)
```

#### `agrag.ingestion.community.required_member_ids` \{#agrag-ingestion-community-required_member_ids}

```python
required_member_ids(communities:list[Community], *, min_importance_for_llm_report:float = _DEFAULT_MIN_IMPORTANCE_FOR_LLM_REPORT, max_members_per_prompt:int = _DEFAULT_MAX_MEMBERS_PER_PROMPT) -> set[UUID]
```

Return the member ids generate_community_reports will actually read.

An LLM-qualifying community only needs its top max_members_per_prompt
members (already ordered by local weight, highest first); a
heuristic-report community only needs its top 3. Since level-0
clusters are capped by max_cluster_size and typically much smaller
than max_members_per_prompt, this mainly saves by excluding isolated
entities and any entity type detect_communities() never touches, not
by truncating within a community.

**Parameters:**

- **communities** (<code>list\[[Community](common.md#agrag-common-data_models-community-Community)\]</code>) – The communities generate_community_reports will run
  over.
- **min_importance_for_llm_report** (<code>float</code>) – Must match the value
  generate_community_reports is called with, or the two
  functions disagree about which communities are LLM-qualifying.
- **max_members_per_prompt** (<code>int</code>) – Must match the value
  generate_community_reports is called with.

**Returns:**

- <code>set\[UUID\]</code> – The union of every community's needed member ids.

### `agrag.ingestion.extract` \{#agrag-ingestion-extract}

The Extractor interface: reads one Chunk and produces an ExtractionResult.

**Classes:**

- [**BAMLExtractor**](#agrag-ingestion-extract-BAMLExtractor) – Extracts entities and relations with an LLM through a typed BAML function.
- [**EscalatingExtractor**](#agrag-ingestion-extract-EscalatingExtractor) – Runs a cheap extractor on every chunk and a stronger one on weak results.
- [**ExtractionLLMSettings**](#agrag-ingestion-extract-ExtractionLLMSettings) – Env-backed LLM client config for the extraction role.
- [**Extractor**](#agrag-ingestion-extract-Extractor) – Reads one chunk and returns the entities and relations it contains.
- [**ExtractorMissingExtraError**](#agrag-ingestion-extract-ExtractorMissingExtraError) – An Extractor needs a package extra that is not installed.
- [**GlinerExtractor**](#agrag-ingestion-extract-GlinerExtractor) – Extracts entities and relations with a local GLiNER2.5 model.

#### `agrag.ingestion.extract.BAMLExtractor` \{#agrag-ingestion-extract-BAMLExtractor}

```python
BAMLExtractor(*, settings:ExtractionLLMSettings | None = None, client:object | None = None, tracer:Tracer | None = None, include_heading_path:bool = True) -> None
```

Bases: <code>[Extractor](#agrag-ingestion-extract-Extractor)</code>

Extracts entities and relations with an LLM through a typed BAML function.

The extractor calls `ExtractEntitiesAndRelations` on the clients in
`ExtractionLLMSettings` and retries failed calls with the settings' backoff.
The response type comes from the graph schema, so the model can return only
declared labels and property keys, and it can fill entity properties. Needs
the `llm` extra and a reachable LLM endpoint.

**Parameters:**

- **settings** (<code>[ExtractionLLMSettings](#agrag-ingestion-extract-ExtractionLLMSettings) | None</code>) – LLM client config. Defaults to `ExtractionLLMSettings()`,
  loaded from the environment or `.env`. Ignored when `client` is
  given; an injected client also disables `settings.retry` because
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

##### `agrag.ingestion.extract.BAMLExtractor.extract` \{#agrag-ingestion-extract-BAMLExtractor-extract}

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract with an LLM call through the configured ClientRegistry.

**Parameters:**

- **chunk** (<code>[Chunk](common.md#agrag-common-data_models-chunk-Chunk)</code>) – The chunk to read. Only `chunk.text` and `chunk.id` are used.
- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The entity and relation types to extract.

**Returns:**

- <code>[ExtractionResult](common.md#agrag-common-data_models-extraction-ExtractionResult)</code> – The normalized entities and relations found in the chunk.

**Raises:**

- <code>[ExtractorMissingExtraError](#agrag-ingestion-extract-ExtractorMissingExtraError)</code> – The `llm` package extra is not
  installed.
- <code>ValueError</code> – `chunk.id` is `None`.

##### `agrag.ingestion.extract.BAMLExtractor.settings` \{#agrag-ingestion-extract-BAMLExtractor-settings}

```python
settings = settings
```

#### `agrag.ingestion.extract.EscalatingExtractor` \{#agrag-ingestion-extract-EscalatingExtractor}

```python
EscalatingExtractor(primary:Extractor, escalate_to:Extractor, *, min_confidence:float = 0.5, min_chunk_words:int = 8, tracer:Tracer | None = None) -> None
```

Bases: <code>[Extractor](#agrag-ingestion-extract-Extractor)</code>

Runs a cheap extractor on every chunk and a stronger one on weak results.

The primary extractor runs first. A chunk escalates when the primary finds no
entities in a chunk of at least `min_chunk_words` words, or when the mean
entity confidence is below `min_confidence`. An escalated chunk gets the
`escalate_to` result alone; the two results are never combined. A common
pairing is `GlinerExtractor` as primary and `BAMLExtractor` as fallback.

**Parameters:**

- **primary** (<code>[Extractor](#agrag-ingestion-extract-Extractor)</code>) – Extractor that runs on every chunk.
- **escalate_to** (<code>[Extractor](#agrag-ingestion-extract-Extractor)</code>) – Extractor that replaces the primary result when escalation
  triggers.
- **min_confidence** (<code>float</code>) – Escalate when the primary's mean reported confidence is
  below this value.
- **min_chunk_words** (<code>int</code>) – Treat an empty primary result as weak only when the
  chunk has at least this many words.
- **tracer** (<code>Tracer | None</code>) – Opens the `agrag.extraction.escalating` span. `None` opens
  no recorded span.

**Functions:**

- [**extract**](#agrag-ingestion-extract-EscalatingExtractor-extract) – Extract with the primary extractor, escalating when it's weak.

**Attributes:**

- [**escalate_to**](#agrag-ingestion-extract-EscalatingExtractor-escalate_to) –
- [**min_chunk_words**](#agrag-ingestion-extract-EscalatingExtractor-min_chunk_words) –
- [**min_confidence**](#agrag-ingestion-extract-EscalatingExtractor-min_confidence) –
- [**primary**](#agrag-ingestion-extract-EscalatingExtractor-primary) –

##### `agrag.ingestion.extract.EscalatingExtractor.escalate_to` \{#agrag-ingestion-extract-EscalatingExtractor-escalate_to}

```python
escalate_to = escalate_to
```

##### `agrag.ingestion.extract.EscalatingExtractor.extract` \{#agrag-ingestion-extract-EscalatingExtractor-extract}

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract with the primary extractor, escalating when it's weak.

**Parameters:**

- **chunk** (<code>[Chunk](common.md#agrag-common-data_models-chunk-Chunk)</code>) – The chunk to read.
- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The entity and relation types to extract.

**Returns:**

- <code>[ExtractionResult](common.md#agrag-common-data_models-extraction-ExtractionResult)</code> – The primary result, or the escalation result when escalation triggers.

##### `agrag.ingestion.extract.EscalatingExtractor.min_chunk_words` \{#agrag-ingestion-extract-EscalatingExtractor-min_chunk_words}

```python
min_chunk_words = min_chunk_words
```

##### `agrag.ingestion.extract.EscalatingExtractor.min_confidence` \{#agrag-ingestion-extract-EscalatingExtractor-min_confidence}

```python
min_confidence = min_confidence
```

##### `agrag.ingestion.extract.EscalatingExtractor.primary` \{#agrag-ingestion-extract-EscalatingExtractor-primary}

```python
primary = primary
```

#### `agrag.ingestion.extract.ExtractionLLMSettings` \{#agrag-ingestion-extract-ExtractionLLMSettings}

Bases: <code>BaseSettings</code>

Env-backed LLM client config for the extraction role.

**Attributes:**

- [**clients**](#agrag-ingestion-extract-ExtractionLLMSettings-clients) (<code>list\[LLMClientConfig\]</code>) – The LLM client(s) to use. One element for a single provider;
  more than one composed per `strategy`.
- [**strategy**](#agrag-ingestion-extract-ExtractionLLMSettings-strategy) (<code>Literal['single', 'fallback', 'round_robin']</code>) – How to compose multiple clients. Ignored with one client.
- [**retry**](#agrag-ingestion-extract-ExtractionLLMSettings-retry) (<code>RetryConfig</code>) – Retry settings applied to the extraction LLM call.

Env prefix: `EXTRACTION_LLM_`.

**Functions:**

- [**from_openai_compatible_env**](#agrag-ingestion-extract-ExtractionLLMSettings-from_openai_compatible_env) – Build settings from a generic OpenAI-compatible endpoint.

##### `agrag.ingestion.extract.ExtractionLLMSettings.clients` \{#agrag-ingestion-extract-ExtractionLLMSettings-clients}

```python
clients: list[LLMClientConfig]
```

##### `agrag.ingestion.extract.ExtractionLLMSettings.from_openai_compatible_env` \{#agrag-ingestion-extract-ExtractionLLMSettings-from_openai_compatible_env}

```python
from_openai_compatible_env() -> ExtractionLLMSettings
```

Build settings from a generic OpenAI-compatible endpoint.

Reads `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL_ID` from the
environment or `.env`, so the model name is never hardcoded. Raises
`RuntimeError` when the required variables are not all set.

**Returns:**

- <code>[ExtractionLLMSettings](#agrag-ingestion-extract-ExtractionLLMSettings)</code> – Settings pointing at one `openai-generic` client.

##### `agrag.ingestion.extract.ExtractionLLMSettings.model_config` \{#agrag-ingestion-extract-ExtractionLLMSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='EXTRACTION_LLM_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

##### `agrag.ingestion.extract.ExtractionLLMSettings.retry` \{#agrag-ingestion-extract-ExtractionLLMSettings-retry}

```python
retry: RetryConfig = Field(default_factory=RetryConfig)
```

##### `agrag.ingestion.extract.ExtractionLLMSettings.strategy` \{#agrag-ingestion-extract-ExtractionLLMSettings-strategy}

```python
strategy: Literal['single', 'fallback', 'round_robin'] = 'single'
```

#### `agrag.ingestion.extract.Extractor` \{#agrag-ingestion-extract-Extractor}

Bases: <code>ABC</code>

Reads one chunk and returns the entities and relations it contains.

<details class="note" open markdown="1">
<summary>Note</summary>

Subclass this class to provide custom extraction. `Graph` awaits
`extract` once for each chunk. The built-in extractors are
`GlinerExtractor` (a local model), `BAMLExtractor` (an LLM call),
and `EscalatingExtractor` (a cheap extractor first, a stronger one
when the result is weak).

</details>

**Functions:**

- [**extract**](#agrag-ingestion-extract-Extractor-extract) – Extract entities and relations from one chunk.

##### `agrag.ingestion.extract.Extractor.extract` \{#agrag-ingestion-extract-Extractor-extract}

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract entities and relations from one chunk.

**Parameters:**

- **chunk** (<code>[Chunk](common.md#agrag-common-data_models-chunk-Chunk)</code>) – The chunk to read. Only `chunk.text` and `chunk.id` are used.
- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The entity/relation types to extract. Every returned entity's
  `label` and relation's `label` must be declared in this schema.

**Returns:**

- <code>[ExtractionResult](common.md#agrag-common-data_models-extraction-ExtractionResult)</code> – The entities and relations this call found, in extraction order.

#### `agrag.ingestion.extract.ExtractorMissingExtraError` \{#agrag-ingestion-extract-ExtractorMissingExtraError}

```python
ExtractorMissingExtraError(component:str, extra:str) -> None
```

Bases: <code>[IngestionError](loaders.md#agrag-loaders-corpus-errors-IngestionError)</code>

An Extractor needs a package extra that is not installed.

**Attributes:**

- [**component**](#agrag-ingestion-extract-ExtractorMissingExtraError-component) – The class name that needs the extra.
- [**extra**](#agrag-ingestion-extract-ExtractorMissingExtraError-extra) – The package extra to install.

##### `agrag.ingestion.extract.ExtractorMissingExtraError.component` \{#agrag-ingestion-extract-ExtractorMissingExtraError-component}

```python
component = component
```

##### `agrag.ingestion.extract.ExtractorMissingExtraError.extra` \{#agrag-ingestion-extract-ExtractorMissingExtraError-extra}

```python
extra = extra
```

#### `agrag.ingestion.extract.GlinerExtractor` \{#agrag-ingestion-extract-GlinerExtractor}

```python
GlinerExtractor(*, model_name:str = 'fastino/gliner2.5-small-v1', model:object | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Extractor](#agrag-ingestion-extract-Extractor)</code>

Extracts entities and relations with a local GLiNER2.5 model.

The model runs in this process, so extraction needs no LLM key. It loads on
first use and one load serves concurrent calls. The first load downloads the
weights from Hugging Face unless `model` is passed. GLiNER reports entity
spans and types, so extracted entities carry no property values. Needs the
`extract` extra.

**Parameters:**

- **model_name** (<code>str</code>) – Checkpoint to load when `model` is not provided.
- **model** (<code>object | None</code>) – An already-built GLiNER2.5 model.
- **tracer** (<code>Tracer | None</code>) – Opens `agrag.extraction.gliner` and
  `agrag.extraction.model_load` spans. `None` opens no recorded
  span.

**Functions:**

- [**extract**](#agrag-ingestion-extract-GlinerExtractor-extract) – Extract with the local GLiNER2.5 model.

**Attributes:**

- [**model_name**](#agrag-ingestion-extract-GlinerExtractor-model_name) –

##### `agrag.ingestion.extract.GlinerExtractor.extract` \{#agrag-ingestion-extract-GlinerExtractor-extract}

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract with the local GLiNER2.5 model.

**Parameters:**

- **chunk** (<code>[Chunk](common.md#agrag-common-data_models-chunk-Chunk)</code>) – The chunk to read. Only `chunk.text` and `chunk.id` are used.
- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The entity and relation types to extract.

**Returns:**

- <code>[ExtractionResult](common.md#agrag-common-data_models-extraction-ExtractionResult)</code> – The normalized entities and relations found in the chunk.

**Raises:**

- <code>[ExtractorMissingExtraError](#agrag-ingestion-extract-ExtractorMissingExtraError)</code> – The `extract` package extra is not
  installed.
- <code>ValueError</code> – `chunk.id` is `None`.

##### `agrag.ingestion.extract.GlinerExtractor.model_name` \{#agrag-ingestion-extract-GlinerExtractor-model_name}

```python
model_name = model_name
```

### `agrag.ingestion.graph` \{#agrag-ingestion-graph}

The public Graph API for ingestion.

**Classes:**

- [**Graph**](#agrag-ingestion-graph-Graph) – A knowledge graph that a caller can open and add content to.

**Attributes:**

- [**SYSTEM_RELATION_TYPES**](#agrag-ingestion-graph-SYSTEM_RELATION_TYPES) –
- [**SourceType**](#agrag-ingestion-graph-SourceType) –
- [**SourcesType**](#agrag-ingestion-graph-SourcesType) –

#### `agrag.ingestion.graph.Graph` \{#agrag-ingestion-graph-Graph}

```python
Graph(*, schema:GraphSchema, graph_store:GraphStore, embedder:Embedder, extractor:Extractor, tracer:Tracer | None = None, vector_store:VectorStore | None = None, retrieval_settings:RetrievalSettings | None = None, cutover_settings:CutoverJobSettings | None = None, chunking:Chunking = DEFAULT_CHUNKING, embed_heading_path:bool = True, max_llm_pairs:int = MAX_LLM_PAIRS) -> None
```

A knowledge graph that a caller can open and add content to.

When an optional VectorStore is configured, every embedding this
graph writes to graph_store is also upserted there, so SearchEngine's
VectorStore path finds the same vectors the GraphStore-native path
does. Collections follow RetrievalSettings' names and are provisioned
by `open()` when missing.

**Functions:**

- [**add**](#agrag-ingestion-graph-Graph-add) – Add content to the graph.
- [**consolidate**](#agrag-ingestion-graph-Graph-consolidate) – Run non-destructive resolution against every persisted raw entity.
- [**deactivate_match**](#agrag-ingestion-graph-Graph-deactivate_match) – Deactivate a semantic match and synchronize replacement retrieval vectors.
- [**delete_document**](#agrag-ingestion-graph-Graph-delete_document) – Soft-delete a document by closing its current PART_OF edges.
- [**detect_communities**](#agrag-ingestion-graph-Graph-detect_communities) – Detect entity communities via hierarchical Leiden.
- [**open**](#agrag-ingestion-graph-Graph-open) – Open a graph, connecting and fully provisioning graph_store.
- [**reevaluate**](#agrag-ingestion-graph-Graph-reevaluate) – Reevaluate matches among the given entities, adding and removing edges.
- [**update**](#agrag-ingestion-graph-Graph-update) – Replace one document version, closing its former PART_OF edges.

**Attributes:**

- [**chunking**](#agrag-ingestion-graph-Graph-chunking) (<code>[Chunking](chunking.md#agrag-chunking-Chunking)</code>) – The rules that pick a chunker for each document.

**Parameters:**

- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The entity/relation types this graph validates every
  extraction against.
- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Where entities, relations, chunks, and MENTIONED_IN
  edges are written.
- **embedder** (<code>[Embedder](embedding.md#agrag-embedding-base-Embedder)</code>) – Populates entity embeddings for native vector search.
- **extractor** (<code>[Extractor](#agrag-ingestion-extract-Extractor)</code>) – Runs against each chunk.
- **tracer** (<code>Tracer | None</code>) – A tracer to record spans for every step. Pass None for none.
- **vector_store** (<code>[VectorStore](vectordb.md#agrag-vectordb-base-VectorStore) | None</code>) – Optional second write target for embeddings. When
  set, every embedding the pipeline writes to graph_store is
  also upserted here, so SearchEngine's VectorStore path finds
  the same vectors the GraphStore-native path does. Also gets
  old community vectors removed on each
  detect_communities(apply=True) cycle.
- **retrieval_settings** (<code>[RetrievalSettings](retrieval.md#agrag-retrieval-settings-RetrievalSettings) | None</code>) – Collection names for the VectorStore writes.
  None uses RetrievalSettings defaults. Ignored when
  vector_store is None.
- **cutover_settings** (<code>[CutoverJobSettings](#agrag-ingestion-settings-CutoverJobSettings) | None</code>) – Lease configuration for the Cutover Jobs
  add/update/delete_document run through. None uses
  CutoverJobSettings defaults.
- **chunking** (<code>[Chunking](chunking.md#agrag-chunking-Chunking)</code>) – The rules that pick a chunker for each document. The
  default is `DEFAULT_CHUNKING`.
- **embed_heading_path** (<code>bool</code>) – Whether chunk embeddings include the chunk's
  heading path above its text. The stored text does not change.
  Existing embeddings stay until a document is re-chunked with
  `update()`.
- **max_llm_pairs** (<code>int</code>) – The most ambiguous entity pairs that resolution sends
  to the LLM for each label. A lower value bounds the number of
  verification calls and leaves more pairs undecided.

##### `agrag.ingestion.graph.Graph.add` \{#agrag-ingestion-graph-Graph-add}

```python
add(source:SourcesType | None = None, *, text:str | None = None, documents:Sequence[Document] | None = None, loader:Loader | None = None, error_policy:ErrorPolicy = ErrorPolicy.RAISE, on_progress:Callable[[AddResult], None] | None = None, return_chunks:bool = False, read_options:ReadOptions | None = None) -> AddResult
```

Add content to the graph.

Give exactly one of `source`, `text`, and `documents`.

**Parameters:**

- **source** (<code>[SourcesType](#agrag-ingestion-graph-SourcesType) | None</code>) – A file path, a directory, a glob, or a list of these.
- **text** (<code>str | None</code>) – Raw text to add as one document.
- **documents** (<code>Sequence\[[Document](common.md#agrag-common-data_models-document-Document)\] | None</code>) – Already-built documents to add directly.
- **loader** (<code>[Loader](loaders.md#agrag-loaders-corpus-base-Loader) | None</code>) – A loader to use instead of the registry default. Requires a
  single-file `source`; a directory, glob, or list of sources raises an
  error.
- **error_policy** (<code>[ErrorPolicy](loaders.md#agrag-loaders-corpus-types-ErrorPolicy)</code>) – The action to take on a per-source error.
- **on_progress** (<code>Callable\[\[[AddResult](#agrag-ingestion-reports-AddResult)\], None\] | None</code>) – A callback the call runs after each batch and once more
  at the end with the fully-populated result.
- **return_chunks** (<code>bool</code>) – Whether to include the produced chunks in the
  returned AddResult. False by default to avoid holding full text
  for a large corpus when not needed.
- **read_options** (<code>[ReadOptions](loaders.md#agrag-loaders-corpus-types-ReadOptions) | None</code>) – How loaders read sources, including the normalization of
  decoded text. None uses `ReadOptions()` defaults.

**Returns:**

- <code>[AddResult](#agrag-ingestion-reports-AddResult)</code> – A summary of what was added per pipeline stage. Resolution runs
- **automatically** (<code>[AddResult](#agrag-ingestion-reports-AddResult)</code>) – exact identity plus fuzzy, embedding, and
- <code>[AddResult](#agrag-ingestion-reports-AddResult)</code> – capped LLM zones over one combined mention list, with
- <code>[AddResult](#agrag-ingestion-reports-AddResult)</code> – confirmed matches persisted as MATCHES edges and derived
- <code>[AddResult](#agrag-ingestion-reports-AddResult)</code> – ResolvedEntity nodes. LLM verification calls stay bounded
- <code>[AddResult](#agrag-ingestion-reports-AddResult)</code> – at ceil(L * MAX_LLM_PAIRS / 10) requests for L labels;
- <code>[AddResult](#agrag-ingestion-reports-AddResult)</code> – inspect result.resolution.ambiguous_count for the pairs no
- <code>[AddResult](#agrag-ingestion-reports-AddResult)</code> – tier could decide.

**Raises:**

- <code>ValueError</code> – The call got zero, or more than one, of `source`, `text`,
  and `documents`. Also raised when `loader` is set without
  `source`, or with a source that can match more than one file.
- <code>UnsupportedFormatError</code> – No loader is registered for a source's format.
- <code>MissingExtraError</code> – A loader is registered for a source's format, but its
  package extra is not installed. This error follows `error_policy`
  instead of always stopping the call.
- <code>ValueError</code> – The input contains multiple documents with the same
  `document_key`.

##### `agrag.ingestion.graph.Graph.chunking` \{#agrag-ingestion-graph-Graph-chunking}

```python
chunking: Chunking
```

The rules that pick a chunker for each document.

##### `agrag.ingestion.graph.Graph.consolidate` \{#agrag-ingestion-graph-Graph-consolidate}

```python
consolidate(*, apply:bool = False) -> ConsolidationReport
```

Run non-destructive resolution against every persisted raw entity.

Dry-run by default: produces matches before any node is touched. Pass
apply=True to write MATCHES edges and derived ResolvedEntity nodes.

For each EntityType label in self.\_schema, fetches every persisted
entity with that label, bounds the pairs actually compared with
GraphCandidateSource's ANN-backed persisted_candidate_indices, and
runs the same zone-routed resolution add() uses (exact, fuzzy
fast-path, embedding similarity, capped LLM review) over those
candidate pairs. Confirmed non-exact matches preserve both raw
Entity nodes and their relationships.

LLM verification calls stay bounded: at most
ceil(L * MAX_LLM_PAIRS / 10) requests for L labels. See Graph.add.

**Parameters:**

- **apply** (<code>bool</code>) – Write the confirmed matches and rebuild resolved entities.
  False produces a report only.

**Returns:**

- <code>[ConsolidationReport](#agrag-ingestion-reports-ConsolidationReport)</code> – A report of every confirmed non-exact match, applied or not,
- <code>[ConsolidationReport](#agrag-ingestion-reports-ConsolidationReport)</code> – plus the count of uncertain LLM verdicts.

##### `agrag.ingestion.graph.Graph.deactivate_match` \{#agrag-ingestion-graph-Graph-deactivate_match}

```python
deactivate_match(match_id:UUID) -> list[ResolvedEntity]
```

Deactivate a semantic match and synchronize replacement retrieval vectors.

##### `agrag.ingestion.graph.Graph.delete_document` \{#agrag-ingestion-graph-Graph-delete_document}

```python
delete_document(document_key:str) -> UpdateResult
```

Soft-delete a document by closing its current PART_OF edges.

Currency is read transitively through `PART_OF`: closing the
open edges removes the document from retrieval while its chunks,
the `Document` node, and contributed entities stay in the graph
for provenance. An unknown `document_key` is a no-op. Entities
mentioned only by this document's chunks lose their last evidence
and are pruned with their shrunken clusters. The close and the
prune run as one job's commit and cleanup, so a crash either
leaves the document untouched or completes the deletion.

**Parameters:**

- **document_key** (<code>str</code>) – The stable key of the document to delete.

**Returns:**

- <code>[UpdateResult](#agrag-ingestion-reports-UpdateResult)</code> – The deletion summary: `no_op=True` when nothing was stored
- <code>[UpdateResult](#agrag-ingestion-reports-UpdateResult)</code> – under the key, otherwise `chunks_closed` with
- <code>[UpdateResult](#agrag-ingestion-reports-UpdateResult)</code> – `new_content_hash=None` and no `add_result`.

<details class="note" open markdown="1">
<summary>Note</summary>

The close-only degenerate case of `Graph.update()`; both
call into the same shared document-lifecycle helpers. See
`Graph.add()` for the shared ingestion behavior.

</details>

##### `agrag.ingestion.graph.Graph.detect_communities` \{#agrag-ingestion-graph-Graph-detect_communities}

```python
detect_communities(*, apply:bool = False, max_cluster_size:int = 10, resolution:float = 1.0, seed:int | None = 3735928559) -> CommunityDetectionReport
```

Detect entity communities via hierarchical Leiden.

Dry-run by default: produces a report of the communities that would be
written before any node is touched. Pass apply=True to write them.

Fetches every live domain relation across the whole graph (not scoped
by entity label the way consolidate() is -- community structure spans
entity types), builds a weighted edge list, and runs hierarchical
Leiden off the event loop. Every prior run's Community nodes and
MEMBER_OF edges are deleted before the new ones are written when
apply=True: this is a full recompute, not an incremental update,
so there is no notion of merging this run's output with a
previous one's.

**Parameters:**

- **apply** (<code>bool</code>) – Write the computed communities. False produces a report only.
- **max_cluster_size** (<code>int</code>) – Forwarded to compute_communities.
- **resolution** (<code>float</code>) – Forwarded to compute_communities.
- **seed** (<code>int | None</code>) – Forwarded to compute_communities.

**Returns:**

- <code>[CommunityDetectionReport](#agrag-ingestion-reports-CommunityDetectionReport)</code> – A report of every community this call found, applied or not.

**Raises:**

- <code>[CommunityDetectionMissingExtraError](#agrag-ingestion-community-CommunityDetectionMissingExtraError)</code> –
  graspologic-native is not installed.

##### `agrag.ingestion.graph.Graph.open` \{#agrag-ingestion-graph-Graph-open}

```python
open(*, schema:GraphSchema, graph_store:GraphStore, embedder:Embedder, extractor:Extractor, tracer:Tracer | None = None, vector_store:VectorStore | None = None, retrieval_settings:RetrievalSettings | None = None, cutover_settings:CutoverJobSettings | None = None, chunking:Chunking = DEFAULT_CHUNKING, embed_heading_path:bool = True, max_llm_pairs:int = MAX_LLM_PAIRS) -> Graph
```

Open a graph, connecting and fully provisioning graph_store.

Provisioning order: connect, then register every label/relation type
this graph will ever write (schema's own labels/types plus the fixed
system names CHUNK_LABEL/SYSTEM_RELATION_TYPES), then
setup_constraints(), then setup_indexes(), then vector indexes for
every schema entity label — so a brand-new database is fully ready,
including the merge_key uniqueness constraints the global exact-match
tier relies on and the embedding vector indexes native search needs,
before this call returns. When vector_store is set, the entity, chunk,
and community collections are provisioned there too (created when
missing) so the dual writes never hit an absent collection.

**Parameters:**

- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The entity/relation types this graph validates every
  extraction against.
- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Where entities, relations, chunks, and MENTIONED_IN
  edges are written.
- **embedder** (<code>[Embedder](embedding.md#agrag-embedding-base-Embedder)</code>) – Populates entity embeddings for native vector search.
- **extractor** (<code>[Extractor](#agrag-ingestion-extract-Extractor)</code>) – Runs against each chunk.
- **tracer** (<code>Tracer | None</code>) – A tracer to record spans for every step. Pass None for none.
- **vector_store** (<code>[VectorStore](vectordb.md#agrag-vectordb-base-VectorStore) | None</code>) – Optional second write target for embeddings; see
  __init__.
- **retrieval_settings** (<code>[RetrievalSettings](retrieval.md#agrag-retrieval-settings-RetrievalSettings) | None</code>) – Collection names for the VectorStore writes.
  None uses RetrievalSettings defaults.
- **cutover_settings** (<code>[CutoverJobSettings](#agrag-ingestion-settings-CutoverJobSettings) | None</code>) – Lease configuration for the Cutover Jobs
  add/update/delete_document run through. None uses
  CutoverJobSettings defaults.
- **chunking** (<code>[Chunking](chunking.md#agrag-chunking-Chunking)</code>) – The rules that pick a chunker for each document; see
  __init__.
- **embed_heading_path** (<code>bool</code>) – Whether chunk embeddings include the heading path;
  see __init__.
- **max_llm_pairs** (<code>int</code>) – The most ambiguous entity pairs sent to the LLM for each
  label during resolution; see __init__.

**Returns:**

- <code>[Graph](#agrag-ingestion-graph-Graph)</code> – A graph connected to graph_store and ready to accept add() calls.

**Raises:**

- <code>EmbeddingDimensionMismatchError</code> – A vector index in graph_store
  already exists with a different dimension than the embedder
  produces.
- <code>CollectionDimensionMismatchError</code> – A vector_store collection
  already exists with a different dimension than the embedder
  produces.
- <code>Exception</code> – Whatever connect(), registration, constraint/index
  setup, or vector-index provisioning raises. graph_store is
  closed first, so a failed open() never leaks a connection.

##### `agrag.ingestion.graph.Graph.reevaluate` \{#agrag-ingestion-graph-Graph-reevaluate}

```python
reevaluate(entity_ids:list[UUID]) -> ReevaluationReport
```

Reevaluate matches among the given entities, adding and removing edges.

Fetches exactly the supplied entities, compares same-label pairs
only among this set through one zone-routed Resolver pass, writes
confirmed matches that lack an active edge, and deactivates active
edges among the set the resolver did not confirm. Exact-text pairs
never gain or lose edges. Nothing outside the input set is compared
or touched, and nothing calls this automatically.

LLM verification calls stay bounded at ceil(L * MAX_LLM_PAIRS / 10)
requests for L labels, as in Graph.add.

**Parameters:**

- **entity_ids** (<code>list\[UUID\]</code>) – The persisted entities to reevaluate, deduped with
  input order preserved.

**Returns:**

- <code>[ReevaluationReport](#agrag-ingestion-reports-ReevaluationReport)</code> – Which entities were reevaluated, which matches were added,
- <code>[ReevaluationReport](#agrag-ingestion-reports-ReevaluationReport)</code> – which match edges were deactivated, and how many inputs had no
- <code>[ReevaluationReport](#agrag-ingestion-reports-ReevaluationReport)</code> – incident added or removed edge.

**Raises:**

- <code>ValueError</code> – An id has no live persisted entity.

##### `agrag.ingestion.graph.Graph.update` \{#agrag-ingestion-graph-Graph-update}

```python
update(document_key:str, *, text:str | None = None, source:SourcesType | None = None, loader:Loader | None = None, error_policy:ErrorPolicy = ErrorPolicy.RAISE, read_options:ReadOptions | None = None) -> UpdateResult
```

Replace one document version, closing its former PART_OF edges.

Looks up the persisted `Document` node by `document_key`. An
unchanged content hash is a no-op returning before any chunking,
extraction, or writes, unless the chunker that this graph's rules pick
for the document differs from the one that made its current chunks. A
chunker with new settings re-chunks the document as a content change
does. Chunks written before chunkers were recorded count as unchanged.
Otherwise the fresh content ingests under a Cutover Job holding this
document's lease, and the commit flips the job, closes the document's
open `PART_OF` edges, and clears every pending tag in one
transaction — so a crash either leaves
the old version untouched or completes the replacement including
cleanup. Entities that lose their last evidence are pruned after
the commit, so replacement mentions count as evidence. A source
must resolve to exactly one document.

**Parameters:**

- **document_key** (<code>str</code>) – The stable key of the document to replace.
- **text** (<code>str | None</code>) – Replacement text, exactly one of `text`/`source`.
- **source** (<code>[SourcesType](#agrag-ingestion-graph-SourcesType) | None</code>) – A single-file source, glob, or path list resolving to
  exactly one document.
- **loader** (<code>[Loader](loaders.md#agrag-loaders-corpus-base-Loader) | None</code>) – A loader override for a single-file `source`.
- **error_policy** (<code>[ErrorPolicy](loaders.md#agrag-loaders-corpus-types-ErrorPolicy)</code>) – RAISE propagates a stage failure; any other
  policy records it and continues.
- **read_options** (<code>[ReadOptions](loaders.md#agrag-loaders-corpus-types-ReadOptions) | None</code>) – How loaders read the replacement, including the
  normalization of its text. None uses `ReadOptions()` defaults.

**Returns:**

- <code>[UpdateResult](#agrag-ingestion-reports-UpdateResult)</code> – The update summary. A no-op reports `no_op=True` with no
- <code>[UpdateResult](#agrag-ingestion-reports-UpdateResult)</code> – `add_result`; a change reports `chunks_closed` plus the
- <code>[UpdateResult](#agrag-ingestion-reports-UpdateResult)</code> – fresh ingestion's `add_result`; an unknown `document_key`
- <code>[UpdateResult](#agrag-ingestion-reports-UpdateResult)</code> – ingests fresh with `previous_content_hash=None` and
- <code>[UpdateResult](#agrag-ingestion-reports-UpdateResult)</code> – `chunks_closed=0`.

**Raises:**

- <code>ValueError</code> – Both or neither of `text` and `source` are given, a loader
  override targets multiple sources, or a source resolves to any number
  of documents other than one.

<details class="note" open markdown="1">
<summary>Note</summary>

The fresh-content path shares `ingest_chunks()` with
`Graph.add()`; both callers observe the same pipeline behavior
for the same input.

</details>

#### `agrag.ingestion.graph.SYSTEM_RELATION_TYPES` \{#agrag-ingestion-graph-SYSTEM_RELATION_TYPES}

```python
SYSTEM_RELATION_TYPES = ['MENTIONED_IN', MEMBER_OF_RELATION, 'PART_OF', 'NEXT_CHUNK', 'MATCHES', 'RESOLVED_AS']
```

#### `agrag.ingestion.graph.SourceType` \{#agrag-ingestion-graph-SourceType}

```python
SourceType = Union[str, Path]
```

#### `agrag.ingestion.graph.SourcesType` \{#agrag-ingestion-graph-SourcesType}

```python
SourcesType = Union[SourceType, Sequence[SourceType]]
```

### `agrag.ingestion.merge` \{#agrag-ingestion-merge}

Merge mechanics: computing how a resolved group of mentions and entities combine.

This module is storage-agnostic: it decides what a merge should look like,
but never touches GraphStore itself. Applying a computed MergePlan is a
separate step.

**Classes:**

- [**ConflictRecord**](#agrag-ingestion-merge-ConflictRecord) – One property that had more than one candidate value.
- [**MergePlan**](#agrag-ingestion-merge-MergePlan) – Computed result of merging zero or more entities and mentions.
- [**PropertyRules**](#agrag-ingestion-merge-PropertyRules) – Per-property conflict resolution, with a default for unlisted properties.
- [**PropertyStrategy**](#agrag-ingestion-merge-PropertyStrategy) – Fallback rule for a property with no entry in PropertyRules.

**Functions:**

- [**apply_merge**](#agrag-ingestion-merge-apply_merge) – Write a computed MergePlan to storage.
- [**compute_merge**](#agrag-ingestion-merge-compute_merge) – Compute how existing_entities and mentions combine into one Entity.
- [**mentioned_in_id**](#agrag-ingestion-merge-mentioned_in_id) – Return the deterministic id for a new Chunk -[:MENTIONED_IN]-> Entity edge.
- [**merge_properties**](#agrag-ingestion-merge-merge_properties) – Return field-resolved properties and records of every real conflict.
- [**next_chunk_id**](#agrag-ingestion-merge-next_chunk_id) – Return the deterministic id for a Chunk -[:NEXT_CHUNK]-> Chunk edge.
- [**part_of_id**](#agrag-ingestion-merge-part_of_id) – Return the id for one versioned Document -[:PART_OF]-> Chunk edge.
- [**relation_id**](#agrag-ingestion-merge-relation_id) – Return the deterministic id for a domain relationship triple.
- [**resolve_description**](#agrag-ingestion-merge-resolve_description) – Resolve a description field, trying LLM summarization.
- [**select_canonical**](#agrag-ingestion-merge-select_canonical) – Return the canonical entity and the rest, from two or more entities.

**Attributes:**

- [**PropertyRule**](#agrag-ingestion-merge-PropertyRule) – Per-property conflict resolver.

#### `agrag.ingestion.merge.ConflictRecord` \{#agrag-ingestion-merge-ConflictRecord}

Bases: <code>BaseModel</code>

One property that had more than one candidate value.

**Attributes:**

- [**field**](#agrag-ingestion-merge-ConflictRecord-field) (<code>str</code>) – The property name.
- [**candidates**](#agrag-ingestion-merge-ConflictRecord-candidates) (<code>list\[object\]</code>) – Every distinct candidate value seen, in encounter order.
- [**resolved**](#agrag-ingestion-merge-ConflictRecord-resolved) (<code>object</code>) – The value compute_merge chose.

##### `agrag.ingestion.merge.ConflictRecord.candidates` \{#agrag-ingestion-merge-ConflictRecord-candidates}

```python
candidates: list[object]
```

##### `agrag.ingestion.merge.ConflictRecord.field` \{#agrag-ingestion-merge-ConflictRecord-field}

```python
field: str
```

##### `agrag.ingestion.merge.ConflictRecord.resolved` \{#agrag-ingestion-merge-ConflictRecord-resolved}

```python
resolved: object
```

#### `agrag.ingestion.merge.MergePlan` \{#agrag-ingestion-merge-MergePlan}

Bases: <code>BaseModel</code>

Computed result of merging zero or more entities and mentions.

**Attributes:**

- [**survivor**](#agrag-ingestion-merge-MergePlan-survivor) (<code>[Entity](common.md#agrag-common-data_models-entity-Entity)</code>) – The resulting Entity. Its merge_count and
  source_chunk_ids are this call's best local computation, for
  reporting; apply_merge writes new_source_chunk_ids and
  merge_count_delta atomically instead, so a concurrent writer's
  own contribution to the same node is never overwritten.
- [**conflicts**](#agrag-ingestion-merge-MergePlan-conflicts) (<code>list\[[ConflictRecord](#agrag-ingestion-merge-ConflictRecord)\]</code>) – Every field that had more than one candidate value.
- [**accepted_merge_keys**](#agrag-ingestion-merge-MergePlan-accepted_merge_keys) (<code>list\[str\]</code>) – Every normalized merge_key this merge
  accepted -- from existing_entities and mentions alike, not only
  the survivor's own chosen name -- so a later mention of any
  accepted name resolves back to this entity instead of creating
  a duplicate.
- [**new_source_chunk_ids**](#agrag-ingestion-merge-MergePlan-new_source_chunk_ids) (<code>list\[UUID\]</code>) – The chunk ids this call's mentions contribute,
  applied as an atomic union against whatever the survivor's node
  currently has.
- [**merge_count_delta**](#agrag-ingestion-merge-MergePlan-merge_count_delta) (<code>int</code>) – The amount to atomically add to whatever
  merge_count the survivor's node currently has.

##### `agrag.ingestion.merge.MergePlan.accepted_merge_keys` \{#agrag-ingestion-merge-MergePlan-accepted_merge_keys}

```python
accepted_merge_keys: list[str] = []
```

##### `agrag.ingestion.merge.MergePlan.conflicts` \{#agrag-ingestion-merge-MergePlan-conflicts}

```python
conflicts: list[ConflictRecord] = []
```

##### `agrag.ingestion.merge.MergePlan.merge_count_delta` \{#agrag-ingestion-merge-MergePlan-merge_count_delta}

```python
merge_count_delta: int = 0
```

##### `agrag.ingestion.merge.MergePlan.new_source_chunk_ids` \{#agrag-ingestion-merge-MergePlan-new_source_chunk_ids}

```python
new_source_chunk_ids: list[UUID] = []
```

##### `agrag.ingestion.merge.MergePlan.survivor` \{#agrag-ingestion-merge-MergePlan-survivor}

```python
survivor: Entity
```

#### `agrag.ingestion.merge.PropertyRule` \{#agrag-ingestion-merge-PropertyRule}

```python
PropertyRule = Callable[[list[object]], object]
```

Per-property conflict resolver.

Takes every candidate value for one property, in encounter order, already
filtered to exclude None, and returns the resolved value.

#### `agrag.ingestion.merge.PropertyRules` \{#agrag-ingestion-merge-PropertyRules}

```python
PropertyRules(rules:dict[str, PropertyRule] = dict(), default:PropertyStrategy = PropertyStrategy.KEEP_FIRST) -> None
```

Per-property conflict resolution, with a default for unlisted properties.

**Attributes:**

- [**rules**](#agrag-ingestion-merge-PropertyRules-rules) (<code>dict\[str, [PropertyRule](#agrag-ingestion-merge-PropertyRule)\]</code>) – Property name to resolver, for properties needing a specific rule.
- [**default**](#agrag-ingestion-merge-PropertyRules-default) (<code>[PropertyStrategy](#agrag-ingestion-merge-PropertyStrategy)</code>) – Strategy applied to a property with no entry in rules.

##### `agrag.ingestion.merge.PropertyRules.default` \{#agrag-ingestion-merge-PropertyRules-default}

```python
default: PropertyStrategy = PropertyStrategy.KEEP_FIRST
```

##### `agrag.ingestion.merge.PropertyRules.rules` \{#agrag-ingestion-merge-PropertyRules-rules}

```python
rules: dict[str, PropertyRule] = field(default_factory=dict)
```

#### `agrag.ingestion.merge.PropertyStrategy` \{#agrag-ingestion-merge-PropertyStrategy}

Bases: <code>StrEnum</code>

Fallback rule for a property with no entry in PropertyRules.

**Attributes:**

- [**KEEP_FIRST**](#agrag-ingestion-merge-PropertyStrategy-KEEP_FIRST) –
- [**KEEP_LAST**](#agrag-ingestion-merge-PropertyStrategy-KEEP_LAST) –
- [**MERGE_ALL**](#agrag-ingestion-merge-PropertyStrategy-MERGE_ALL) –

##### `agrag.ingestion.merge.PropertyStrategy.KEEP_FIRST` \{#agrag-ingestion-merge-PropertyStrategy-KEEP_FIRST}

```python
KEEP_FIRST = 'keep_first'
```

##### `agrag.ingestion.merge.PropertyStrategy.KEEP_LAST` \{#agrag-ingestion-merge-PropertyStrategy-KEEP_LAST}

```python
KEEP_LAST = 'keep_last'
```

##### `agrag.ingestion.merge.PropertyStrategy.MERGE_ALL` \{#agrag-ingestion-merge-PropertyStrategy-MERGE_ALL}

```python
MERGE_ALL = 'merge_all'
```

#### `agrag.ingestion.merge.apply_merge` \{#agrag-ingestion-merge-apply_merge}

```python
apply_merge(plan:MergePlan, *, graph_store:GraphStore, schema:GraphSchema, pending_job_id:str | None = None) -> None
```

Write a computed MergePlan to storage.

Every call runs inside one GraphStore transaction: it upserts the
survivor and records a merge-key alias for its current name. A
failure partway through leaves no half-written state: no survivor
without its alias.

**Parameters:**

- **plan** (<code>[MergePlan](#agrag-ingestion-merge-MergePlan)</code>) – The merge to write.
- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Where the merge is written.
- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The schema the survivor's label belongs to.
- **pending_job_id** (<code>str | None</code>) – The in-flight Cutover Job's id, tagging the
  survivor node and its aliases until that job commits. None
  writes untagged, for callers outside a job.

**Raises:**

- <code>GraphStoreAliasConflictError</code> – An accepted merge_key is already owned
  by a live entity outside this merge's own survivor id -- a
  concurrent writer accepted that name as an alias of, or
  created it as the canonical name of, a different entity.

#### `agrag.ingestion.merge.compute_merge` \{#agrag-ingestion-merge-compute_merge}

```python
compute_merge(*, existing_entities:list[Entity], mentions:list[ExtractedEntity], schema:GraphSchema, rules:PropertyRules | None = None, description_settings:Any | None = None, description_client:Any | None = None, job_id:UUID | str | None = None, tracer:Tracer | None = None) -> tuple[MergePlan, list[Any]]
```

Compute how existing_entities and mentions combine into one Entity.

No storage is touched. Zero existing entities produces a brand-new Entity.
One produces an updated copy folding in the mentions. Two or more picks a
canonical entity for the survivor's identity; the others contribute
property values and accepted merge-key aliases.

**Parameters:**

- **existing_entities** (<code>list\[[Entity](common.md#agrag-common-data_models-entity-Entity)\]</code>) – Already-persisted entities this call reconciles.
- **mentions** (<code>list\[[ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity)\]</code>) – Fresh ExtractedEntity mentions to fold in.
- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – Used to look up the entity type's declared properties for the
  canonical-id schema-completeness check.
- **rules** (<code>[PropertyRules](#agrag-ingestion-merge-PropertyRules) | None</code>) – Per-property conflict resolution. Defaults to keep_first. The
  name is always a single string: under merge_all it takes the
  canonical entity's name, or the first mention's when none exists.
- **description_settings** (<code>Any | None</code>) – LLM settings for description summarization.
- **description_client** (<code>Any | None</code>) – Injected LLM client for tests.
- **job_id** (<code>UUID | str | None</code>) – The Cutover Job this merge runs under. A brand-new entity
  derives its id from (job_id, merge_key) instead of uuid4, so
  replaying the job after a crash reproduces the same id. None
  keeps today's random-id behavior for callers outside a job.
- **tracer** (<code>Tracer | None</code>) – Passed to description summarization.

**Returns:**

- <code>tuple\[[MergePlan](#agrag-ingestion-merge-MergePlan), list\[Any\]\]</code> – The computed MergePlan and any description-LLM failures.

**Raises:**

- <code>ValueError</code> – existing_entities and mentions are both empty, or their
  labels disagree.

#### `agrag.ingestion.merge.mentioned_in_id` \{#agrag-ingestion-merge-mentioned_in_id}

```python
mentioned_in_id(chunk_id:UUID, entity_id:UUID) -> UUID
```

Return the deterministic id for a new Chunk -[:MENTIONED_IN]-> Entity edge.

Only a fresh id for a pair with no persisted edge yet is guaranteed to equal
this. A caller writing to an already-persisted pair should look up the
edge by its endpoints first and fall back to this id only when none is
found.

**Parameters:**

- **chunk_id** (<code>UUID</code>) – The Chunk's id.
- **entity_id** (<code>UUID</code>) – The Entity's id.

**Returns:**

- <code>UUID</code> – The edge id. Deterministic: same pair always returns same id.

#### `agrag.ingestion.merge.merge_properties` \{#agrag-ingestion-merge-merge_properties}

```python
merge_properties(property_sources:list[dict[str, object]], rules:PropertyRules, *, description_settings:Any | None = None, description_client:Any | None = None, tracer:Tracer | None = None) -> tuple[dict[str, object], list[ConflictRecord], list[Any]]
```

Return field-resolved properties and records of every real conflict.

**Parameters:**

- **property_sources** (<code>list\[dict\[str, object\]\]</code>) – One dict per source entity/mention, keyed by field.
- **rules** (<code>[PropertyRules](#agrag-ingestion-merge-PropertyRules)</code>) – The per-property rule table.
- **description_settings** (<code>Any | None</code>) – LLM settings for description summarization.
- **description_client** (<code>Any | None</code>) – Injected LLM client for tests.
- **tracer** (<code>Tracer | None</code>) – Passed to description summarization.

**Returns:**

- <code>tuple\[dict\[str, object\], list\[[ConflictRecord](#agrag-ingestion-merge-ConflictRecord)\], list\[Any\]\]</code> – The resolved properties, conflict records, and optional stage failures.

#### `agrag.ingestion.merge.next_chunk_id` \{#agrag-ingestion-merge-next_chunk_id}

```python
next_chunk_id(from_chunk_id:UUID, to_chunk_id:UUID) -> UUID
```

Return the deterministic id for a Chunk -[:NEXT_CHUNK]-> Chunk edge.

**Parameters:**

- **from_chunk_id** (<code>UUID</code>) – The id of the earlier chunk in sequence.
- **to_chunk_id** (<code>UUID</code>) – The id of the chunk that follows it.

**Returns:**

- <code>UUID</code> – The edge id. Same pair always returns the same id.

#### `agrag.ingestion.merge.part_of_id` \{#agrag-ingestion-merge-part_of_id}

```python
part_of_id(document_node_id:UUID, chunk_id:UUID, version_id:UUID | str) -> UUID
```

Return the id for one versioned Document -[:PART_OF]-> Chunk edge.

**Parameters:**

- **document_node_id** (<code>UUID</code>) – The id of the Document graph node.
- **chunk_id** (<code>UUID</code>) – The id of the Chunk.
- **version_id** (<code>UUID | str</code>) – The identifier for this document version.

**Returns:**

- <code>UUID</code> – The edge id. Each document version gets a separate relationship id.

#### `agrag.ingestion.merge.relation_id` \{#agrag-ingestion-merge-relation_id}

```python
relation_id(source_id:UUID, target_id:UUID, rel_type:str) -> UUID
```

Return the deterministic id for a domain relationship triple.

Two concurrent `add()` calls resolving the same `(source_id, target_id, rel_type)` triple can both miss the existing-relation lookup
and each try to create it; since this id depends only on the triple, both
writers compute the same one, so `upsert_relation_query`'s `MERGE`
converges to a single edge instead of two parallel ones with unrelated
random ids. Mirrors `mentioned_in_id`.

**Parameters:**

- **source_id** (<code>UUID</code>) – The relationship's source Entity id.
- **target_id** (<code>UUID</code>) – The relationship's target Entity id.
- **rel_type** (<code>str</code>) – The relationship's type.

**Returns:**

- <code>UUID</code> – The relationship id. Same triple always returns the same id.

#### `agrag.ingestion.merge.resolve_description` \{#agrag-ingestion-merge-resolve_description}

```python
resolve_description(candidates:list[object], *, settings:Any | None = None, client:Any | None = None, tracer:Tracer | None = None) -> tuple[object, bool, Any | None]
```

Resolve a description field, trying LLM summarization.

A single distinct candidate needs no LLM call. Multiple candidates try
LLM summarization; on failure, fall back to concatenation.

**Parameters:**

- **candidates** (<code>list\[object\]</code>) – Candidate values in encounter order.
- **settings** (<code>Any | None</code>) – LLM settings for summarization. None uses defaults.
- **client** (<code>Any | None</code>) – An already-built BAML client for tests.
- **tracer** (<code>Tracer | None</code>) – Opens the `agrag.merge.resolve_description` span and the
  LLM call spans below it.

**Returns:**

- <code>tuple\[object, bool, Any | None\]</code> – The resolved value, whether it conflicted, and an optional failure.

#### `agrag.ingestion.merge.select_canonical` \{#agrag-ingestion-merge-select_canonical}

```python
select_canonical(entities:list[Entity], entity_type:EntityType | None) -> tuple[Entity, list[Entity]]
```

Return the canonical entity and the rest, from two or more entities.

Schema-completeness (fewest missing declared fields) first, then earliest
created_at, then lexicographically smallest id.

**Parameters:**

- **entities** (<code>list\[[Entity](common.md#agrag-common-data_models-entity-Entity)\]</code>) – The entities to choose from.
- **entity_type** (<code>[EntityType](common.md#agrag-common-data_models-graph_schema-EntityType) | None</code>) – The schema type for this label, if declared.

**Returns:**

- <code>tuple\[[Entity](common.md#agrag-common-data_models-entity-Entity), list\[[Entity](common.md#agrag-common-data_models-entity-Entity)\]\]</code> – The canonical entity and the other entities.

### `agrag.ingestion.reports` \{#agrag-ingestion-reports}

Reports returned by Graph pipeline operations.

One class per module under this package; this init re-exports them so
`from agrag.ingestion.reports import AddResult` keeps working.

**Modules:**

- [**add_result**](#agrag-ingestion-reports-add_result) – Graph.add()'s result type.
- [**community_detection_report**](#agrag-ingestion-reports-community_detection_report) – Graph.detect_communities()'s result type.
- [**consolidation_report**](#agrag-ingestion-reports-consolidation_report) – Graph.consolidate()'s result type.
- [**reevaluation_report**](#agrag-ingestion-reports-reevaluation_report) – Graph.reevaluate()'s result type.
- [**update_result**](#agrag-ingestion-reports-update_result) – Result returned by document lifecycle operations.

**Classes:**

- [**AddResult**](#agrag-ingestion-reports-AddResult) – Graph.add()'s return type — one summary per pipeline stage.
- [**CommunityDetectionReport**](#agrag-ingestion-reports-CommunityDetectionReport) – Report from Graph.detect_communities().
- [**ConsolidationReport**](#agrag-ingestion-reports-ConsolidationReport) – Report from Graph.consolidate().
- [**ReevaluationReport**](#agrag-ingestion-reports-ReevaluationReport) – Report from Graph.reevaluate().
- [**UpdateResult**](#agrag-ingestion-reports-UpdateResult) – Summary of an update or soft deletion.

#### `agrag.ingestion.reports.AddResult` \{#agrag-ingestion-reports-AddResult}

Bases: <code>BaseModel</code>

Graph.add()'s return type — one summary per pipeline stage.

**Attributes:**

- [**ingestion**](#agrag-ingestion-reports-AddResult-ingestion) (<code>[IngestStats](#agrag-ingestion-stats-IngestStats)</code>) – Ingestion-stage results.
- [**chunking**](#agrag-ingestion-reports-AddResult-chunking) (<code>[ChunkingStats](#agrag-ingestion-stats-ChunkingStats)</code>) – The chunker each document got and the chunks it made.
- [**extraction**](#agrag-ingestion-reports-AddResult-extraction) (<code>[ExtractionStats](#agrag-ingestion-stats-ExtractionStats)</code>) – Extractor output across every chunk this call
  processed.
- [**resolution**](#agrag-ingestion-reports-AddResult-resolution) (<code>[ResolutionStats](#agrag-ingestion-stats-ResolutionStats)</code>) – Resolution's tier-by-tier match counts.
- [**merge**](#agrag-ingestion-reports-AddResult-merge) (<code>[MergeStats](#agrag-ingestion-stats-MergeStats)</code>) – What merge mechanics did with resolution's groups.
- [**storage**](#agrag-ingestion-reports-AddResult-storage) (<code>[StorageStats](#agrag-ingestion-stats-StorageStats)</code>) – What made it to GraphStore, and what didn't.
- [**chunks**](#agrag-ingestion-reports-AddResult-chunks) (<code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code>) – Every Chunk this call produced. Empty unless
  return_chunks=True — holding full chunk text for a large
  corpus is a real memory cost most callers don't need paid
  for.

##### `agrag.ingestion.reports.AddResult.chunking` \{#agrag-ingestion-reports-AddResult-chunking}

```python
chunking: ChunkingStats = Field(default_factory=ChunkingStats)
```

##### `agrag.ingestion.reports.AddResult.chunks` \{#agrag-ingestion-reports-AddResult-chunks}

```python
chunks: list[Chunk] = Field(default_factory=list)
```

##### `agrag.ingestion.reports.AddResult.documents` \{#agrag-ingestion-reports-AddResult-documents}

```python
documents: int
```

Proxy to ingestion.documents for backward compatibility.

##### `agrag.ingestion.reports.AddResult.extraction` \{#agrag-ingestion-reports-AddResult-extraction}

```python
extraction: ExtractionStats = Field(default_factory=ExtractionStats)
```

##### `agrag.ingestion.reports.AddResult.ingestion` \{#agrag-ingestion-reports-AddResult-ingestion}

```python
ingestion: IngestStats = Field(default_factory=IngestStats)
```

##### `agrag.ingestion.reports.AddResult.merge` \{#agrag-ingestion-reports-AddResult-merge}

```python
merge: MergeStats = Field(default_factory=MergeStats)
```

##### `agrag.ingestion.reports.AddResult.quarantined` \{#agrag-ingestion-reports-AddResult-quarantined}

```python
quarantined: int
```

Proxy to ingestion.quarantined for backward compatibility.

##### `agrag.ingestion.reports.AddResult.quarantined_items` \{#agrag-ingestion-reports-AddResult-quarantined_items}

```python
quarantined_items: list[StageFailure]
```

Proxy to ingestion.quarantined_items for backward compatibility.

##### `agrag.ingestion.reports.AddResult.resolution` \{#agrag-ingestion-reports-AddResult-resolution}

```python
resolution: ResolutionStats = Field(default_factory=ResolutionStats)
```

##### `agrag.ingestion.reports.AddResult.skipped` \{#agrag-ingestion-reports-AddResult-skipped}

```python
skipped: int
```

Proxy to ingestion.skipped for backward compatibility.

##### `agrag.ingestion.reports.AddResult.sources` \{#agrag-ingestion-reports-AddResult-sources}

```python
sources: int
```

Proxy to ingestion.sources for backward compatibility.

##### `agrag.ingestion.reports.AddResult.storage` \{#agrag-ingestion-reports-AddResult-storage}

```python
storage: StorageStats = Field(default_factory=StorageStats)
```

#### `agrag.ingestion.reports.CommunityDetectionReport` \{#agrag-ingestion-reports-CommunityDetectionReport}

Bases: <code>BaseModel</code>

Report from Graph.detect_communities().

**Attributes:**

- [**communities**](#agrag-ingestion-reports-CommunityDetectionReport-communities) (<code>list\[[Community](common.md#agrag-common-data_models-community-Community)\]</code>) – The communities this call found, whether applied or not.
- [**applied**](#agrag-ingestion-reports-CommunityDetectionReport-applied) (<code>bool</code>) – Whether the communities were written.
- [**failures**](#agrag-ingestion-reports-CommunityDetectionReport-failures) (<code>list\[[StageFailure](common.md#agrag-common-data_models-stage_failure-StageFailure)\]</code>) – Failures generating an applied community's LLM report or
  embedding its report text. A failed community still gets
  written, with a heuristic report or a missing embedding in
  place of the failed step. Always empty when apply is False.

##### `agrag.ingestion.reports.CommunityDetectionReport.applied` \{#agrag-ingestion-reports-CommunityDetectionReport-applied}

```python
applied: bool = False
```

##### `agrag.ingestion.reports.CommunityDetectionReport.communities` \{#agrag-ingestion-reports-CommunityDetectionReport-communities}

```python
communities: list[Community] = Field(default_factory=list)
```

##### `agrag.ingestion.reports.CommunityDetectionReport.failures` \{#agrag-ingestion-reports-CommunityDetectionReport-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

#### `agrag.ingestion.reports.ConsolidationReport` \{#agrag-ingestion-reports-ConsolidationReport}

Bases: <code>BaseModel</code>

Report from Graph.consolidate().

**Attributes:**

- [**would_match**](#agrag-ingestion-reports-ConsolidationReport-would_match) (<code>list\[[MatchDecision](#agrag-ingestion-resolved_entities-MatchDecision)\]</code>) – Confirmed non-exact matches found, whether applied or not.
- [**applied**](#agrag-ingestion-reports-ConsolidationReport-applied) (<code>bool</code>) – Whether the matches were applied.
- [**failures**](#agrag-ingestion-reports-ConsolidationReport-failures) (<code>list\[[StageFailure](common.md#agrag-common-data_models-stage_failure-StageFailure)\]</code>) – Failures writing a match graph or rebuilding resolved entities.
  Always empty when apply is False.
- [**ambiguous_count**](#agrag-ingestion-reports-ConsolidationReport-ambiguous_count) (<code>int</code>) – LLM verdicts that came back uncertain. These
  pairs never merge.

##### `agrag.ingestion.reports.ConsolidationReport.ambiguous_count` \{#agrag-ingestion-reports-ConsolidationReport-ambiguous_count}

```python
ambiguous_count: int = 0
```

##### `agrag.ingestion.reports.ConsolidationReport.applied` \{#agrag-ingestion-reports-ConsolidationReport-applied}

```python
applied: bool = False
```

##### `agrag.ingestion.reports.ConsolidationReport.failures` \{#agrag-ingestion-reports-ConsolidationReport-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

##### `agrag.ingestion.reports.ConsolidationReport.would_match` \{#agrag-ingestion-reports-ConsolidationReport-would_match}

```python
would_match: list[MatchDecision] = Field(default_factory=list)
```

#### `agrag.ingestion.reports.ReevaluationReport` \{#agrag-ingestion-reports-ReevaluationReport}

Bases: <code>BaseModel</code>

Report from Graph.reevaluate().

**Attributes:**

- [**entities_reevaluated**](#agrag-ingestion-reports-ReevaluationReport-entities_reevaluated) (<code>list\[UUID\]</code>) – Input entity ids reevaluated, deduped with
  input order preserved.
- [**matches_added**](#agrag-ingestion-reports-ReevaluationReport-matches_added) (<code>list\[[MatchDecision](#agrag-ingestion-resolved_entities-MatchDecision)\]</code>) – Confirmed matches with no active edge, now written.
- [**matches_removed**](#agrag-ingestion-reports-ReevaluationReport-matches_removed) (<code>list\[UUID\]</code>) – Ids of active match edges the resolver did not
  confirm, now deactivated.
- [**unchanged_count**](#agrag-ingestion-reports-ReevaluationReport-unchanged_count) (<code>int</code>) – Input entities with no incident added or removed
  edge.

##### `agrag.ingestion.reports.ReevaluationReport.entities_reevaluated` \{#agrag-ingestion-reports-ReevaluationReport-entities_reevaluated}

```python
entities_reevaluated: list[UUID] = Field(default_factory=list)
```

##### `agrag.ingestion.reports.ReevaluationReport.matches_added` \{#agrag-ingestion-reports-ReevaluationReport-matches_added}

```python
matches_added: list[MatchDecision] = Field(default_factory=list)
```

##### `agrag.ingestion.reports.ReevaluationReport.matches_removed` \{#agrag-ingestion-reports-ReevaluationReport-matches_removed}

```python
matches_removed: list[UUID] = Field(default_factory=list)
```

##### `agrag.ingestion.reports.ReevaluationReport.unchanged_count` \{#agrag-ingestion-reports-ReevaluationReport-unchanged_count}

```python
unchanged_count: int = 0
```

#### `agrag.ingestion.reports.UpdateResult` \{#agrag-ingestion-reports-UpdateResult}

Bases: <code>BaseModel</code>

Summary of an update or soft deletion.

**Attributes:**

- [**document_key**](#agrag-ingestion-reports-UpdateResult-document_key) (<code>str</code>) – Stable identity used for the document node.
- [**no_op**](#agrag-ingestion-reports-UpdateResult-no_op) (<code>bool</code>) – Whether no graph changes were needed.
- [**previous_content_hash**](#agrag-ingestion-reports-UpdateResult-previous_content_hash) (<code>str | None</code>) – Hash stored before the operation, if present.
- [**new_content_hash**](#agrag-ingestion-reports-UpdateResult-new_content_hash) (<code>str | None</code>) – Hash written by an update, or `None` on deletion.
- [**chunks_closed**](#agrag-ingestion-reports-UpdateResult-chunks_closed) (<code>int</code>) – Number of open PART_OF edges closed.
- [**add_result**](#agrag-ingestion-reports-UpdateResult-add_result) (<code>[AddResult](#agrag-ingestion-reports-add_result-AddResult) | None</code>) – Ingestion details for changed content, if any.

##### `agrag.ingestion.reports.UpdateResult.add_result` \{#agrag-ingestion-reports-UpdateResult-add_result}

```python
add_result: AddResult | None = None
```

##### `agrag.ingestion.reports.UpdateResult.chunks_closed` \{#agrag-ingestion-reports-UpdateResult-chunks_closed}

```python
chunks_closed: int = 0
```

##### `agrag.ingestion.reports.UpdateResult.document_key` \{#agrag-ingestion-reports-UpdateResult-document_key}

```python
document_key: str
```

##### `agrag.ingestion.reports.UpdateResult.new_content_hash` \{#agrag-ingestion-reports-UpdateResult-new_content_hash}

```python
new_content_hash: str | None = None
```

##### `agrag.ingestion.reports.UpdateResult.no_op` \{#agrag-ingestion-reports-UpdateResult-no_op}

```python
no_op: bool
```

##### `agrag.ingestion.reports.UpdateResult.previous_content_hash` \{#agrag-ingestion-reports-UpdateResult-previous_content_hash}

```python
previous_content_hash: str | None = None
```

#### `agrag.ingestion.reports.add_result` \{#agrag-ingestion-reports-add_result}

Graph.add()'s result type.

**Classes:**

- [**AddResult**](#agrag-ingestion-reports-add_result-AddResult) – Graph.add()'s return type — one summary per pipeline stage.

##### `agrag.ingestion.reports.add_result.AddResult` \{#agrag-ingestion-reports-add_result-AddResult}

Bases: <code>BaseModel</code>

Graph.add()'s return type — one summary per pipeline stage.

**Attributes:**

- [**ingestion**](#agrag-ingestion-reports-add_result-AddResult-ingestion) (<code>[IngestStats](#agrag-ingestion-stats-IngestStats)</code>) – Ingestion-stage results.
- [**chunking**](#agrag-ingestion-reports-add_result-AddResult-chunking) (<code>[ChunkingStats](#agrag-ingestion-stats-ChunkingStats)</code>) – The chunker each document got and the chunks it made.
- [**extraction**](#agrag-ingestion-reports-add_result-AddResult-extraction) (<code>[ExtractionStats](#agrag-ingestion-stats-ExtractionStats)</code>) – Extractor output across every chunk this call
  processed.
- [**resolution**](#agrag-ingestion-reports-add_result-AddResult-resolution) (<code>[ResolutionStats](#agrag-ingestion-stats-ResolutionStats)</code>) – Resolution's tier-by-tier match counts.
- [**merge**](#agrag-ingestion-reports-add_result-AddResult-merge) (<code>[MergeStats](#agrag-ingestion-stats-MergeStats)</code>) – What merge mechanics did with resolution's groups.
- [**storage**](#agrag-ingestion-reports-add_result-AddResult-storage) (<code>[StorageStats](#agrag-ingestion-stats-StorageStats)</code>) – What made it to GraphStore, and what didn't.
- [**chunks**](#agrag-ingestion-reports-add_result-AddResult-chunks) (<code>list\[[Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code>) – Every Chunk this call produced. Empty unless
  return_chunks=True — holding full chunk text for a large
  corpus is a real memory cost most callers don't need paid
  for.

###### `agrag.ingestion.reports.add_result.AddResult.chunking` \{#agrag-ingestion-reports-add_result-AddResult-chunking}

```python
chunking: ChunkingStats = Field(default_factory=ChunkingStats)
```

###### `agrag.ingestion.reports.add_result.AddResult.chunks` \{#agrag-ingestion-reports-add_result-AddResult-chunks}

```python
chunks: list[Chunk] = Field(default_factory=list)
```

###### `agrag.ingestion.reports.add_result.AddResult.documents` \{#agrag-ingestion-reports-add_result-AddResult-documents}

```python
documents: int
```

Proxy to ingestion.documents for backward compatibility.

###### `agrag.ingestion.reports.add_result.AddResult.extraction` \{#agrag-ingestion-reports-add_result-AddResult-extraction}

```python
extraction: ExtractionStats = Field(default_factory=ExtractionStats)
```

###### `agrag.ingestion.reports.add_result.AddResult.ingestion` \{#agrag-ingestion-reports-add_result-AddResult-ingestion}

```python
ingestion: IngestStats = Field(default_factory=IngestStats)
```

###### `agrag.ingestion.reports.add_result.AddResult.merge` \{#agrag-ingestion-reports-add_result-AddResult-merge}

```python
merge: MergeStats = Field(default_factory=MergeStats)
```

###### `agrag.ingestion.reports.add_result.AddResult.quarantined` \{#agrag-ingestion-reports-add_result-AddResult-quarantined}

```python
quarantined: int
```

Proxy to ingestion.quarantined for backward compatibility.

###### `agrag.ingestion.reports.add_result.AddResult.quarantined_items` \{#agrag-ingestion-reports-add_result-AddResult-quarantined_items}

```python
quarantined_items: list[StageFailure]
```

Proxy to ingestion.quarantined_items for backward compatibility.

###### `agrag.ingestion.reports.add_result.AddResult.resolution` \{#agrag-ingestion-reports-add_result-AddResult-resolution}

```python
resolution: ResolutionStats = Field(default_factory=ResolutionStats)
```

###### `agrag.ingestion.reports.add_result.AddResult.skipped` \{#agrag-ingestion-reports-add_result-AddResult-skipped}

```python
skipped: int
```

Proxy to ingestion.skipped for backward compatibility.

###### `agrag.ingestion.reports.add_result.AddResult.sources` \{#agrag-ingestion-reports-add_result-AddResult-sources}

```python
sources: int
```

Proxy to ingestion.sources for backward compatibility.

###### `agrag.ingestion.reports.add_result.AddResult.storage` \{#agrag-ingestion-reports-add_result-AddResult-storage}

```python
storage: StorageStats = Field(default_factory=StorageStats)
```

#### `agrag.ingestion.reports.community_detection_report` \{#agrag-ingestion-reports-community_detection_report}

Graph.detect_communities()'s result type.

**Classes:**

- [**CommunityDetectionReport**](#agrag-ingestion-reports-community_detection_report-CommunityDetectionReport) – Report from Graph.detect_communities().

##### `agrag.ingestion.reports.community_detection_report.CommunityDetectionReport` \{#agrag-ingestion-reports-community_detection_report-CommunityDetectionReport}

Bases: <code>BaseModel</code>

Report from Graph.detect_communities().

**Attributes:**

- [**communities**](#agrag-ingestion-reports-community_detection_report-CommunityDetectionReport-communities) (<code>list\[[Community](common.md#agrag-common-data_models-community-Community)\]</code>) – The communities this call found, whether applied or not.
- [**applied**](#agrag-ingestion-reports-community_detection_report-CommunityDetectionReport-applied) (<code>bool</code>) – Whether the communities were written.
- [**failures**](#agrag-ingestion-reports-community_detection_report-CommunityDetectionReport-failures) (<code>list\[[StageFailure](common.md#agrag-common-data_models-stage_failure-StageFailure)\]</code>) – Failures generating an applied community's LLM report or
  embedding its report text. A failed community still gets
  written, with a heuristic report or a missing embedding in
  place of the failed step. Always empty when apply is False.

###### `agrag.ingestion.reports.community_detection_report.CommunityDetectionReport.applied` \{#agrag-ingestion-reports-community_detection_report-CommunityDetectionReport-applied}

```python
applied: bool = False
```

###### `agrag.ingestion.reports.community_detection_report.CommunityDetectionReport.communities` \{#agrag-ingestion-reports-community_detection_report-CommunityDetectionReport-communities}

```python
communities: list[Community] = Field(default_factory=list)
```

###### `agrag.ingestion.reports.community_detection_report.CommunityDetectionReport.failures` \{#agrag-ingestion-reports-community_detection_report-CommunityDetectionReport-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

#### `agrag.ingestion.reports.consolidation_report` \{#agrag-ingestion-reports-consolidation_report}

Graph.consolidate()'s result type.

**Classes:**

- [**ConsolidationReport**](#agrag-ingestion-reports-consolidation_report-ConsolidationReport) – Report from Graph.consolidate().

##### `agrag.ingestion.reports.consolidation_report.ConsolidationReport` \{#agrag-ingestion-reports-consolidation_report-ConsolidationReport}

Bases: <code>BaseModel</code>

Report from Graph.consolidate().

**Attributes:**

- [**would_match**](#agrag-ingestion-reports-consolidation_report-ConsolidationReport-would_match) (<code>list\[[MatchDecision](#agrag-ingestion-resolved_entities-MatchDecision)\]</code>) – Confirmed non-exact matches found, whether applied or not.
- [**applied**](#agrag-ingestion-reports-consolidation_report-ConsolidationReport-applied) (<code>bool</code>) – Whether the matches were applied.
- [**failures**](#agrag-ingestion-reports-consolidation_report-ConsolidationReport-failures) (<code>list\[[StageFailure](common.md#agrag-common-data_models-stage_failure-StageFailure)\]</code>) – Failures writing a match graph or rebuilding resolved entities.
  Always empty when apply is False.
- [**ambiguous_count**](#agrag-ingestion-reports-consolidation_report-ConsolidationReport-ambiguous_count) (<code>int</code>) – LLM verdicts that came back uncertain. These
  pairs never merge.

###### `agrag.ingestion.reports.consolidation_report.ConsolidationReport.ambiguous_count` \{#agrag-ingestion-reports-consolidation_report-ConsolidationReport-ambiguous_count}

```python
ambiguous_count: int = 0
```

###### `agrag.ingestion.reports.consolidation_report.ConsolidationReport.applied` \{#agrag-ingestion-reports-consolidation_report-ConsolidationReport-applied}

```python
applied: bool = False
```

###### `agrag.ingestion.reports.consolidation_report.ConsolidationReport.failures` \{#agrag-ingestion-reports-consolidation_report-ConsolidationReport-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

###### `agrag.ingestion.reports.consolidation_report.ConsolidationReport.would_match` \{#agrag-ingestion-reports-consolidation_report-ConsolidationReport-would_match}

```python
would_match: list[MatchDecision] = Field(default_factory=list)
```

#### `agrag.ingestion.reports.reevaluation_report` \{#agrag-ingestion-reports-reevaluation_report}

Graph.reevaluate()'s result type.

**Classes:**

- [**ReevaluationReport**](#agrag-ingestion-reports-reevaluation_report-ReevaluationReport) – Report from Graph.reevaluate().

##### `agrag.ingestion.reports.reevaluation_report.ReevaluationReport` \{#agrag-ingestion-reports-reevaluation_report-ReevaluationReport}

Bases: <code>BaseModel</code>

Report from Graph.reevaluate().

**Attributes:**

- [**entities_reevaluated**](#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-entities_reevaluated) (<code>list\[UUID\]</code>) – Input entity ids reevaluated, deduped with
  input order preserved.
- [**matches_added**](#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-matches_added) (<code>list\[[MatchDecision](#agrag-ingestion-resolved_entities-MatchDecision)\]</code>) – Confirmed matches with no active edge, now written.
- [**matches_removed**](#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-matches_removed) (<code>list\[UUID\]</code>) – Ids of active match edges the resolver did not
  confirm, now deactivated.
- [**unchanged_count**](#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-unchanged_count) (<code>int</code>) – Input entities with no incident added or removed
  edge.

###### `agrag.ingestion.reports.reevaluation_report.ReevaluationReport.entities_reevaluated` \{#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-entities_reevaluated}

```python
entities_reevaluated: list[UUID] = Field(default_factory=list)
```

###### `agrag.ingestion.reports.reevaluation_report.ReevaluationReport.matches_added` \{#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-matches_added}

```python
matches_added: list[MatchDecision] = Field(default_factory=list)
```

###### `agrag.ingestion.reports.reevaluation_report.ReevaluationReport.matches_removed` \{#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-matches_removed}

```python
matches_removed: list[UUID] = Field(default_factory=list)
```

###### `agrag.ingestion.reports.reevaluation_report.ReevaluationReport.unchanged_count` \{#agrag-ingestion-reports-reevaluation_report-ReevaluationReport-unchanged_count}

```python
unchanged_count: int = 0
```

#### `agrag.ingestion.reports.update_result` \{#agrag-ingestion-reports-update_result}

Result returned by document lifecycle operations.

**Classes:**

- [**UpdateResult**](#agrag-ingestion-reports-update_result-UpdateResult) – Summary of an update or soft deletion.

##### `agrag.ingestion.reports.update_result.UpdateResult` \{#agrag-ingestion-reports-update_result-UpdateResult}

Bases: <code>BaseModel</code>

Summary of an update or soft deletion.

**Attributes:**

- [**document_key**](#agrag-ingestion-reports-update_result-UpdateResult-document_key) (<code>str</code>) – Stable identity used for the document node.
- [**no_op**](#agrag-ingestion-reports-update_result-UpdateResult-no_op) (<code>bool</code>) – Whether no graph changes were needed.
- [**previous_content_hash**](#agrag-ingestion-reports-update_result-UpdateResult-previous_content_hash) (<code>str | None</code>) – Hash stored before the operation, if present.
- [**new_content_hash**](#agrag-ingestion-reports-update_result-UpdateResult-new_content_hash) (<code>str | None</code>) – Hash written by an update, or `None` on deletion.
- [**chunks_closed**](#agrag-ingestion-reports-update_result-UpdateResult-chunks_closed) (<code>int</code>) – Number of open PART_OF edges closed.
- [**add_result**](#agrag-ingestion-reports-update_result-UpdateResult-add_result) (<code>[AddResult](#agrag-ingestion-reports-add_result-AddResult) | None</code>) – Ingestion details for changed content, if any.

###### `agrag.ingestion.reports.update_result.UpdateResult.add_result` \{#agrag-ingestion-reports-update_result-UpdateResult-add_result}

```python
add_result: AddResult | None = None
```

###### `agrag.ingestion.reports.update_result.UpdateResult.chunks_closed` \{#agrag-ingestion-reports-update_result-UpdateResult-chunks_closed}

```python
chunks_closed: int = 0
```

###### `agrag.ingestion.reports.update_result.UpdateResult.document_key` \{#agrag-ingestion-reports-update_result-UpdateResult-document_key}

```python
document_key: str
```

###### `agrag.ingestion.reports.update_result.UpdateResult.new_content_hash` \{#agrag-ingestion-reports-update_result-UpdateResult-new_content_hash}

```python
new_content_hash: str | None = None
```

###### `agrag.ingestion.reports.update_result.UpdateResult.no_op` \{#agrag-ingestion-reports-update_result-UpdateResult-no_op}

```python
no_op: bool
```

###### `agrag.ingestion.reports.update_result.UpdateResult.previous_content_hash` \{#agrag-ingestion-reports-update_result-UpdateResult-previous_content_hash}

```python
previous_content_hash: str | None = None
```

### `agrag.ingestion.resolve` \{#agrag-ingestion-resolve}

Entity resolution public API.

**Modules:**

- [**batch_validation**](#agrag-ingestion-resolve-batch_validation) – Validation for LLM batch entity-match verdicts.
- [**candidate_source**](#agrag-ingestion-resolve-candidate_source) – Candidate generation for in-batch and persisted graph entities.
- [**comparators**](#agrag-ingestion-resolve-comparators) – Comparison strategies used by entity resolution.
- [**exact_groups**](#agrag-ingestion-resolve-exact_groups) – Exact-name grouping for permanent raw entity records.
- [**resolver**](#agrag-ingestion-resolve-resolver) – Entity resolution: deciding which ExtractedEntity mentions are the same thing.
- [**zone_classifier**](#agrag-ingestion-resolve-zone_classifier) – Zone classification for entity-resolution candidate pairs.

**Classes:**

- [**CandidateSource**](#agrag-ingestion-resolve-CandidateSource) – Narrows which in-batch entity pairs resolution compares.
- [**Comparator**](#agrag-ingestion-resolve-Comparator) – One matching strategy a Resolver runs against a candidate pair.
- [**ComparisonResult**](#agrag-ingestion-resolve-ComparisonResult) – The verdict and evidence produced by one comparator.
- [**ComparisonVerdict**](#agrag-ingestion-resolve-ComparisonVerdict) – A Comparator's verdict on one entity pair.
- [**ExactMatch**](#agrag-ingestion-resolve-ExactMatch) – Matches when normalized text is identical. Never returns NO_MATCH.
- [**FuzzyMatch**](#agrag-ingestion-resolve-FuzzyMatch) – Fast-path accepter for near-identical names. Never returns NO_MATCH.
- [**GraphCandidateSource**](#agrag-ingestion-resolve-GraphCandidateSource) – Blocks by label in-batch; ANN-searches persisted entities globally.
- [**LLMVerify**](#agrag-ingestion-resolve-LLMVerify) – Asks an LLM to verify an ambiguous pair. Last resort; never UNCERTAIN.
- [**PersistedCandidateSource**](#agrag-ingestion-resolve-PersistedCandidateSource) – Supplies only candidate pairs between new mentions and raw graph entities.
- [**ResolutionGroup**](#agrag-ingestion-resolve-ResolutionGroup) – One set of ExtractedEntity indices resolution decided are the same entity.
- [**ResolutionResult**](#agrag-ingestion-resolve-ResolutionResult) – The groups, non-exact evidence, and ambiguity count of one pass.
- [**ResolvedMatch**](#agrag-ingestion-resolve-ResolvedMatch) – One confirmed non-exact match between two input entity indices.
- [**Resolver**](#agrag-ingestion-resolve-Resolver) – Routes blocked candidate pairs through exact, fuzzy, embedding, and LLM zones.

**Functions:**

- [**build_relation_neighbors**](#agrag-ingestion-resolve-build_relation_neighbors) – Build LLMVerify neighbor context from one batch's extracted relations.
- [**exact_match_lookup**](#agrag-ingestion-resolve-exact_match_lookup) – Return persisted exact matches, including accepted merge-key aliases.
- [**exact_resolution_groups**](#agrag-ingestion-resolve-exact_resolution_groups) – Group mentions only when they share exact raw-entity identity.
- [**fetch_persisted_neighbors**](#agrag-ingestion-resolve-fetch_persisted_neighbors) – Fetch a bounded neighbor-relationship sample for persisted entities.
- [**persisted_candidate_indices**](#agrag-ingestion-resolve-persisted_candidate_indices) – Return ANN candidate indices, with a bounded exhaustive fallback.

#### `agrag.ingestion.resolve.CandidateSource` \{#agrag-ingestion-resolve-CandidateSource}

Bases: <code>ABC</code>

Narrows which in-batch entity pairs resolution compares.

**Functions:**

- [**candidates_for**](#agrag-ingestion-resolve-CandidateSource-candidates_for) – Return indices worth comparing against `entities[index]`.

##### `agrag.ingestion.resolve.CandidateSource.candidates_for` \{#agrag-ingestion-resolve-CandidateSource-candidates_for}

```python
candidates_for(index:int, entities:list[ExtractedEntity]) -> list[int]
```

Return indices worth comparing against `entities[index]`.

#### `agrag.ingestion.resolve.Comparator` \{#agrag-ingestion-resolve-Comparator}

Bases: <code>ABC</code>

One matching strategy a Resolver runs against a candidate pair.

**Functions:**

- [**compare**](#agrag-ingestion-resolve-Comparator-compare) – Compare two entities.
- [**compare_with_evidence**](#agrag-ingestion-resolve-Comparator-compare_with_evidence) – Compare two entities and retain any available decision evidence.

##### `agrag.ingestion.resolve.Comparator.compare` \{#agrag-ingestion-resolve-Comparator-compare}

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Compare two entities.

**Parameters:**

- **a** (<code>[ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity)</code>) – The first entity.
- **b** (<code>[ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity)</code>) – The second entity.

**Returns:**

- <code>[ComparisonVerdict](#agrag-ingestion-resolve-resolver-ComparisonVerdict)</code> – This comparator's verdict. UNCERTAIN defers to the next comparator.

##### `agrag.ingestion.resolve.Comparator.compare_with_evidence` \{#agrag-ingestion-resolve-Comparator-compare_with_evidence}

```python
compare_with_evidence(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonResult
```

Compare two entities and retain any available decision evidence.

#### `agrag.ingestion.resolve.ComparisonResult` \{#agrag-ingestion-resolve-ComparisonResult}

Bases: <code>BaseModel</code>

The verdict and evidence produced by one comparator.

**Attributes:**

- [**reasoning**](#agrag-ingestion-resolve-ComparisonResult-reasoning) (<code>str | None</code>) –
- [**score**](#agrag-ingestion-resolve-ComparisonResult-score) (<code>float | None</code>) –
- [**verdict**](#agrag-ingestion-resolve-ComparisonResult-verdict) (<code>[ComparisonVerdict](#agrag-ingestion-resolve-resolver-ComparisonVerdict)</code>) –

##### `agrag.ingestion.resolve.ComparisonResult.reasoning` \{#agrag-ingestion-resolve-ComparisonResult-reasoning}

```python
reasoning: str | None = None
```

##### `agrag.ingestion.resolve.ComparisonResult.score` \{#agrag-ingestion-resolve-ComparisonResult-score}

```python
score: float | None = None
```

##### `agrag.ingestion.resolve.ComparisonResult.verdict` \{#agrag-ingestion-resolve-ComparisonResult-verdict}

```python
verdict: ComparisonVerdict
```

#### `agrag.ingestion.resolve.ComparisonVerdict` \{#agrag-ingestion-resolve-ComparisonVerdict}

Bases: <code>StrEnum</code>

A Comparator's verdict on one entity pair.

**Attributes:**

- [**MATCH**](#agrag-ingestion-resolve-ComparisonVerdict-MATCH) – The comparator is confident these are the same entity.
- [**NO_MATCH**](#agrag-ingestion-resolve-ComparisonVerdict-NO_MATCH) – The comparator is confident these are different entities.
- [**UNCERTAIN**](#agrag-ingestion-resolve-ComparisonVerdict-UNCERTAIN) – This comparator can't decide; the next one gets a turn.

##### `agrag.ingestion.resolve.ComparisonVerdict.MATCH` \{#agrag-ingestion-resolve-ComparisonVerdict-MATCH}

```python
MATCH = 'match'
```

##### `agrag.ingestion.resolve.ComparisonVerdict.NO_MATCH` \{#agrag-ingestion-resolve-ComparisonVerdict-NO_MATCH}

```python
NO_MATCH = 'no_match'
```

##### `agrag.ingestion.resolve.ComparisonVerdict.UNCERTAIN` \{#agrag-ingestion-resolve-ComparisonVerdict-UNCERTAIN}

```python
UNCERTAIN = 'uncertain'
```

#### `agrag.ingestion.resolve.ExactMatch` \{#agrag-ingestion-resolve-ExactMatch}

Bases: <code>[Comparator](#agrag-ingestion-resolve-resolver-Comparator)</code>

Matches when normalized text is identical. Never returns NO_MATCH.

**Functions:**

- [**compare**](#agrag-ingestion-resolve-ExactMatch-compare) – Return MATCH on identical normalized text, else UNCERTAIN.
- [**compare_with_evidence**](#agrag-ingestion-resolve-ExactMatch-compare_with_evidence) – Compare two entities and retain any available decision evidence.

##### `agrag.ingestion.resolve.ExactMatch.compare` \{#agrag-ingestion-resolve-ExactMatch-compare}

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Return MATCH on identical normalized text, else UNCERTAIN.

##### `agrag.ingestion.resolve.ExactMatch.compare_with_evidence` \{#agrag-ingestion-resolve-ExactMatch-compare_with_evidence}

```python
compare_with_evidence(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonResult
```

Compare two entities and retain any available decision evidence.

#### `agrag.ingestion.resolve.FuzzyMatch` \{#agrag-ingestion-resolve-FuzzyMatch}

```python
FuzzyMatch(*, match_above:float = 0.97) -> None
```

Bases: <code>[Comparator](#agrag-ingestion-resolve-resolver-Comparator)</code>

Fast-path accepter for near-identical names. Never returns NO_MATCH.

Rejection belongs to later tiers, which see embedding and LLM evidence
this comparator lacks.

**Attributes:**

- [**match_above**](#agrag-ingestion-resolve-FuzzyMatch-match_above) – A similarity score at or above this is a match.

**Functions:**

- [**compare**](#agrag-ingestion-resolve-FuzzyMatch-compare) – Return a verdict from token-sort-ratio similarity.
- [**compare_with_evidence**](#agrag-ingestion-resolve-FuzzyMatch-compare_with_evidence) – Compare two entities and include their token-sort similarity.

##### `agrag.ingestion.resolve.FuzzyMatch.compare` \{#agrag-ingestion-resolve-FuzzyMatch-compare}

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Return a verdict from token-sort-ratio similarity.

##### `agrag.ingestion.resolve.FuzzyMatch.compare_with_evidence` \{#agrag-ingestion-resolve-FuzzyMatch-compare_with_evidence}

```python
compare_with_evidence(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonResult
```

Compare two entities and include their token-sort similarity.

##### `agrag.ingestion.resolve.FuzzyMatch.match_above` \{#agrag-ingestion-resolve-FuzzyMatch-match_above}

```python
match_above = match_above
```

#### `agrag.ingestion.resolve.GraphCandidateSource` \{#agrag-ingestion-resolve-GraphCandidateSource}

```python
GraphCandidateSource(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, vector_collection:str = '', entity_labels:Sequence[str] = (), top_k:int = 50) -> None
```

Bases: <code>[CandidateSource](#agrag-ingestion-resolve-candidate_source-CandidateSource)</code>

Blocks by label in-batch; ANN-searches persisted entities globally.

**Functions:**

- [**candidates_for**](#agrag-ingestion-resolve-GraphCandidateSource-candidates_for) – Return every other mention sharing the indexed mention's label.
- [**global_candidates_for**](#agrag-ingestion-resolve-GraphCandidateSource-global_candidates_for) – Return persisted entities found by the shared vector-search route.

**Attributes:**

- [**embedder**](#agrag-ingestion-resolve-GraphCandidateSource-embedder) –
- [**entity_labels**](#agrag-ingestion-resolve-GraphCandidateSource-entity_labels) –
- [**graph_store**](#agrag-ingestion-resolve-GraphCandidateSource-graph_store) –
- [**top_k**](#agrag-ingestion-resolve-GraphCandidateSource-top_k) –
- [**vector_collection**](#agrag-ingestion-resolve-GraphCandidateSource-vector_collection) –
- [**vector_store**](#agrag-ingestion-resolve-GraphCandidateSource-vector_store) –

##### `agrag.ingestion.resolve.GraphCandidateSource.candidates_for` \{#agrag-ingestion-resolve-GraphCandidateSource-candidates_for}

```python
candidates_for(index:int, entities:list[ExtractedEntity]) -> list[int]
```

Return every other mention sharing the indexed mention's label.

##### `agrag.ingestion.resolve.GraphCandidateSource.embedder` \{#agrag-ingestion-resolve-GraphCandidateSource-embedder}

```python
embedder = embedder
```

##### `agrag.ingestion.resolve.GraphCandidateSource.entity_labels` \{#agrag-ingestion-resolve-GraphCandidateSource-entity_labels}

```python
entity_labels = tuple(entity_labels)
```

##### `agrag.ingestion.resolve.GraphCandidateSource.global_candidates_for` \{#agrag-ingestion-resolve-GraphCandidateSource-global_candidates_for}

```python
global_candidates_for(mention:ExtractedEntity) -> list[tuple[Entity, float]]
```

Return persisted entities found by the shared vector-search route.

The GraphStore-native path's payload already carries the real node
properties and is validated directly. The VectorStore path's payload
only carries `label` and `text` (the embedding source text), so
candidates are loaded from the graph by hit id instead; a hit that
fails to load, for example a deleted node, is
skipped rather than reconstructed from `text`.

Each candidate is paired with the cosine similarity of the
`VectorHit` it came from. The association is keyed by hit id, never
by position: either branch can drop an entity (malformed payload,
label mismatch, failed load) without dropping the corresponding
score, so zipping the two lists positionally would silently shift
scores onto the wrong entities.

**Returns:**

- <code>list\[tuple\[[Entity](common.md#agrag-common-data_models-entity-Entity), float\]\]</code> – `(Entity, score)` pairs in hit order. `score` is `0.0` for
- <code>list\[tuple\[[Entity](common.md#agrag-common-data_models-entity-Entity), float\]\]</code> – an entity whose id is absent from the hit map, which should not
- <code>list\[tuple\[[Entity](common.md#agrag-common-data_models-entity-Entity), float\]\]</code> – happen since candidate ids come from those same hits.

##### `agrag.ingestion.resolve.GraphCandidateSource.graph_store` \{#agrag-ingestion-resolve-GraphCandidateSource-graph_store}

```python
graph_store = graph_store
```

##### `agrag.ingestion.resolve.GraphCandidateSource.top_k` \{#agrag-ingestion-resolve-GraphCandidateSource-top_k}

```python
top_k = top_k
```

##### `agrag.ingestion.resolve.GraphCandidateSource.vector_collection` \{#agrag-ingestion-resolve-GraphCandidateSource-vector_collection}

```python
vector_collection = vector_collection
```

##### `agrag.ingestion.resolve.GraphCandidateSource.vector_store` \{#agrag-ingestion-resolve-GraphCandidateSource-vector_store}

```python
vector_store = vector_store
```

#### `agrag.ingestion.resolve.LLMVerify` \{#agrag-ingestion-resolve-LLMVerify}

```python
LLMVerify(*, chunks_by_id:dict[UUID, Chunk], settings:ExtractionLLMSettings | None = None, client:object | None = None, max_pairs_per_batch:int = 50, tracer:Tracer | None = None) -> None
```

Bases: <code>[Comparator](#agrag-ingestion-resolve-resolver-Comparator)</code>

Asks an LLM to verify an ambiguous pair. Last resort; never UNCERTAIN.

Never raises from an LLM-call failure: it resolves to NO_MATCH instead, by
the same fail-safe design as every comparator a Resolver runs — an
ambiguous or failed comparison never merges two entities. A missing package
extra is a configuration error, not an ambiguous judgment call, and is
raised outright instead (see compare's Raises section).

**Functions:**

- [**compare**](#agrag-ingestion-resolve-LLMVerify-compare) – Return the LLM's verdict for one pair, or NO_MATCH on failure.
- [**compare_batch**](#agrag-ingestion-resolve-LLMVerify-compare_batch) – Verify ambiguous candidate pairs across bounded LLM requests.
- [**compare_batch_detailed**](#agrag-ingestion-resolve-LLMVerify-compare_batch_detailed) – Verify pairs and count how many verdicts came back uncertain.
- [**compare_with_evidence**](#agrag-ingestion-resolve-LLMVerify-compare_with_evidence) – Compare two entities and retain any available decision evidence.

**Attributes:**

- [**chunks_by_id**](#agrag-ingestion-resolve-LLMVerify-chunks_by_id) –
- [**failed_requests**](#agrag-ingestion-resolve-LLMVerify-failed_requests) (<code>int</code>) –
- [**max_pairs_per_batch**](#agrag-ingestion-resolve-LLMVerify-max_pairs_per_batch) –
- [**settings**](#agrag-ingestion-resolve-LLMVerify-settings) –

**Parameters:**

- **chunks_by_id** (<code>dict\[UUID, [Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code>) – Maps a Chunk id to the Chunk, for prompt context.
- **settings** (<code>[ExtractionLLMSettings](#agrag-ingestion-extract-ExtractionLLMSettings) | None</code>) – LLM client config. Defaults to `ExtractionLLMSettings()`.
  Ignored when `client` is given: an injected client also
  disables `settings.retry`, since a caller building its own
  client is assumed to own its own retry behavior too.
- **client** (<code>object | None</code>) – An already-built BAML client. Tests inject a fake here.
- **max_pairs_per_batch** (<code>int</code>) – Maximum pairs sent to the LLM in one request.
  A large ambiguous population is split into requests of at most
  this size so one oversized request cannot exceed the model's
  context limit and silently fail every pair in the batch.
- **tracer** (<code>Tracer | None</code>) – Opens the `agrag.resolution.llm_verify` span and the
  LLM call spans below it.

##### `agrag.ingestion.resolve.LLMVerify.chunks_by_id` \{#agrag-ingestion-resolve-LLMVerify-chunks_by_id}

```python
chunks_by_id = chunks_by_id
```

##### `agrag.ingestion.resolve.LLMVerify.compare` \{#agrag-ingestion-resolve-LLMVerify-compare}

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Return the LLM's verdict for one pair, or NO_MATCH on failure.

Runs through compare_batch so the single-pair path shares the
batch validation and fail-safe behavior.

**Raises:**

- <code>[ExtractorMissingExtraError](#agrag-ingestion-extract-ExtractorMissingExtraError)</code> – The `llm` package extra is not
  installed.

##### `agrag.ingestion.resolve.LLMVerify.compare_batch` \{#agrag-ingestion-resolve-LLMVerify-compare_batch}

```python
compare_batch(pairs:list[tuple[int, int, ExtractedEntity, ExtractedEntity]], *, similarities:dict[tuple[int, int], float] | None = None, neighbors_by_index:dict[int, list[str]] | None = None) -> dict[tuple[int, int], ComparisonResult]
```

Verify ambiguous candidate pairs across bounded LLM requests.

Splits into requests of at most `max_pairs_per_batch` pairs so one
oversized population cannot exceed the model's context limit.
Invalid, missing, and uncertain model responses do not merge entities.

**Parameters:**

- **pairs** (<code>list\[tuple\[int, int, [ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity), [ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity)\]\]</code>) – `(left_index, right_index, left, right)` tuples to verify.
- **similarities** (<code>dict\[tuple\[int, int\], float\] | None</code>) – Embedding similarity per pair, sent to the model
  as decision context. Defaults to 0.0 when unknown.
- **neighbors_by_index** (<code>dict\[int, list\[str\]\] | None</code>) – Entity index to its neighboring-relationship
  context strings. Looked up globally, so every chunk sees the
  same map.

##### `agrag.ingestion.resolve.LLMVerify.compare_batch_detailed` \{#agrag-ingestion-resolve-LLMVerify-compare_batch_detailed}

```python
compare_batch_detailed(pairs:list[tuple[int, int, ExtractedEntity, ExtractedEntity]], *, similarities:dict[tuple[int, int], float] | None = None, neighbors_by_index:dict[int, list[str]] | None = None) -> tuple[dict[tuple[int, int], ComparisonResult], int]
```

Verify pairs and count how many verdicts came back uncertain.

**Parameters:**

- **pairs** (<code>list\[tuple\[int, int, [ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity), [ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity)\]\]</code>) – The candidate pairs to verify.
- **similarities** (<code>dict\[tuple\[int, int\], float\] | None</code>) – Embedding similarity per pair, sent to the model
  as decision context. Defaults to 0.0 when unknown.
- **neighbors_by_index** (<code>dict\[int, list\[str\]\] | None</code>) – Entity index to its neighboring-relationship
  context strings. Looked up globally, so every chunk sees the
  same map.

**Returns:**

- <code>dict\[tuple\[int, int\], [ComparisonResult](#agrag-ingestion-resolve-resolver-ComparisonResult)\]</code> – The per-pair results and the count of raw uncertain verdicts,
- <code>int</code> – before the fail-safe maps them to NO_MATCH. A request that
- <code>tuple\[dict\[tuple\[int, int\], [ComparisonResult](#agrag-ingestion-resolve-resolver-ComparisonResult)\], int\]</code> – errors maps its pairs to NO_MATCH and increments
- <code>tuple\[dict\[tuple\[int, int\], [ComparisonResult](#agrag-ingestion-resolve-resolver-ComparisonResult)\], int\]</code> – failed_requests.

##### `agrag.ingestion.resolve.LLMVerify.compare_with_evidence` \{#agrag-ingestion-resolve-LLMVerify-compare_with_evidence}

```python
compare_with_evidence(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonResult
```

Compare two entities and retain any available decision evidence.

##### `agrag.ingestion.resolve.LLMVerify.failed_requests` \{#agrag-ingestion-resolve-LLMVerify-failed_requests}

```python
failed_requests: int = 0
```

##### `agrag.ingestion.resolve.LLMVerify.max_pairs_per_batch` \{#agrag-ingestion-resolve-LLMVerify-max_pairs_per_batch}

```python
max_pairs_per_batch = max_pairs_per_batch
```

##### `agrag.ingestion.resolve.LLMVerify.settings` \{#agrag-ingestion-resolve-LLMVerify-settings}

```python
settings = settings
```

#### `agrag.ingestion.resolve.PersistedCandidateSource` \{#agrag-ingestion-resolve-PersistedCandidateSource}

```python
PersistedCandidateSource(candidates_by_index:dict[int, list[int]]) -> None
```

Bases: <code>[CandidateSource](#agrag-ingestion-resolve-candidate_source-CandidateSource)</code>

Supplies only candidate pairs between new mentions and raw graph entities.

**Functions:**

- [**candidates_for**](#agrag-ingestion-resolve-PersistedCandidateSource-candidates_for) – Return persisted candidates for a newly extracted mention.

**Attributes:**

- [**candidates_by_index**](#agrag-ingestion-resolve-PersistedCandidateSource-candidates_by_index) –

##### `agrag.ingestion.resolve.PersistedCandidateSource.candidates_by_index` \{#agrag-ingestion-resolve-PersistedCandidateSource-candidates_by_index}

```python
candidates_by_index = candidates_by_index
```

##### `agrag.ingestion.resolve.PersistedCandidateSource.candidates_for` \{#agrag-ingestion-resolve-PersistedCandidateSource-candidates_for}

```python
candidates_for(index:int, entities:list[ExtractedEntity]) -> list[int]
```

Return persisted candidates for a newly extracted mention.

#### `agrag.ingestion.resolve.ResolutionGroup` \{#agrag-ingestion-resolve-ResolutionGroup}

Bases: <code>BaseModel</code>

One set of ExtractedEntity indices resolution decided are the same entity.

**Attributes:**

- [**entity_indices**](#agrag-ingestion-resolve-ResolutionGroup-entity_indices) (<code>list\[int\]</code>) – Indices into the entity list passed to Resolver.resolve.
  A group of one means resolution found no match for that entity.

##### `agrag.ingestion.resolve.ResolutionGroup.entity_indices` \{#agrag-ingestion-resolve-ResolutionGroup-entity_indices}

```python
entity_indices: list[int]
```

#### `agrag.ingestion.resolve.ResolutionResult` \{#agrag-ingestion-resolve-ResolutionResult}

Bases: <code>BaseModel</code>

The groups, non-exact evidence, and ambiguity count of one pass.

**Attributes:**

- [**groups**](#agrag-ingestion-resolve-ResolutionResult-groups) (<code>list\[[ResolutionGroup](#agrag-ingestion-resolve-resolver-ResolutionGroup)\]</code>) – One group per transitively connected mention set.
- [**matches**](#agrag-ingestion-resolve-ResolutionResult-matches) (<code>list\[[ResolvedMatch](#agrag-ingestion-resolve-resolver-ResolvedMatch)\]</code>) – Evidence for every confirmed non-exact pair.
- [**ambiguous_count**](#agrag-ingestion-resolve-ResolutionResult-ambiguous_count) (<code>int</code>) – LLM verdicts that came back uncertain. These
  pairs never merge.
- [**failed_llm_requests**](#agrag-ingestion-resolve-ResolutionResult-failed_llm_requests) (<code>int</code>) – LLM verification requests that errored
  and were mapped to "no match".
- [**cap_truncated_pairs**](#agrag-ingestion-resolve-ResolutionResult-cap_truncated_pairs) (<code>int</code>) – Boundary pairs that never reached the LLM
  because of the per-label pair cap.

##### `agrag.ingestion.resolve.ResolutionResult.ambiguous_count` \{#agrag-ingestion-resolve-ResolutionResult-ambiguous_count}

```python
ambiguous_count: int = 0
```

##### `agrag.ingestion.resolve.ResolutionResult.cap_truncated_pairs` \{#agrag-ingestion-resolve-ResolutionResult-cap_truncated_pairs}

```python
cap_truncated_pairs: int = 0
```

##### `agrag.ingestion.resolve.ResolutionResult.failed_llm_requests` \{#agrag-ingestion-resolve-ResolutionResult-failed_llm_requests}

```python
failed_llm_requests: int = 0
```

##### `agrag.ingestion.resolve.ResolutionResult.groups` \{#agrag-ingestion-resolve-ResolutionResult-groups}

```python
groups: list[ResolutionGroup]
```

##### `agrag.ingestion.resolve.ResolutionResult.matches` \{#agrag-ingestion-resolve-ResolutionResult-matches}

```python
matches: list[ResolvedMatch]
```

#### `agrag.ingestion.resolve.ResolvedMatch` \{#agrag-ingestion-resolve-ResolvedMatch}

Bases: <code>BaseModel</code>

One confirmed non-exact match between two input entity indices.

Exact-name identity matches group mentions but do not create a match-graph
edge. Every other confirmed comparator decision creates one record.

**Attributes:**

- [**comparator**](#agrag-ingestion-resolve-ResolvedMatch-comparator) (<code>str</code>) –
- [**decided_at**](#agrag-ingestion-resolve-ResolvedMatch-decided_at) (<code>datetime</code>) –
- [**left_index**](#agrag-ingestion-resolve-ResolvedMatch-left_index) (<code>int</code>) –
- [**reasoning**](#agrag-ingestion-resolve-ResolvedMatch-reasoning) (<code>str | None</code>) –
- [**right_index**](#agrag-ingestion-resolve-ResolvedMatch-right_index) (<code>int</code>) –
- [**score**](#agrag-ingestion-resolve-ResolvedMatch-score) (<code>float | None</code>) –

##### `agrag.ingestion.resolve.ResolvedMatch.comparator` \{#agrag-ingestion-resolve-ResolvedMatch-comparator}

```python
comparator: str
```

##### `agrag.ingestion.resolve.ResolvedMatch.decided_at` \{#agrag-ingestion-resolve-ResolvedMatch-decided_at}

```python
decided_at: datetime
```

##### `agrag.ingestion.resolve.ResolvedMatch.left_index` \{#agrag-ingestion-resolve-ResolvedMatch-left_index}

```python
left_index: int
```

##### `agrag.ingestion.resolve.ResolvedMatch.reasoning` \{#agrag-ingestion-resolve-ResolvedMatch-reasoning}

```python
reasoning: str | None = None
```

##### `agrag.ingestion.resolve.ResolvedMatch.right_index` \{#agrag-ingestion-resolve-ResolvedMatch-right_index}

```python
right_index: int
```

##### `agrag.ingestion.resolve.ResolvedMatch.score` \{#agrag-ingestion-resolve-ResolvedMatch-score}

```python
score: float | None = None
```

#### `agrag.ingestion.resolve.Resolver` \{#agrag-ingestion-resolve-Resolver}

```python
Resolver(*, comparators:list[Comparator], candidate_source:CandidateSource, embedder:Embedder | None = None, hard_merge_threshold:float = HARD_MERGE_THRESHOLD, discard_threshold:float = DISCARD_THRESHOLD, max_llm_pairs:int = MAX_LLM_PAIRS, llm_batch_size:int = 10, tracer:Tracer | None = None) -> None
```

Routes blocked candidate pairs through exact, fuzzy, embedding, and LLM zones.

Exact identity groups mentions without evidence. A near-identical
fuzzy score merges on the fast path. Every other pair consults its
embedding cosine similarity: at or above the hard-merge threshold it
merges, below the discard threshold it drops, and inside the band it
needs LLM review, capped per label. Tight ambiguous sub-clusters
merge without spending LLM calls.

**Functions:**

- [**resolve**](#agrag-ingestion-resolve-Resolver-resolve) – Resolve entity groups and retain each confirmed non-exact match.

**Attributes:**

- [**candidate_source**](#agrag-ingestion-resolve-Resolver-candidate_source) –
- [**comparators**](#agrag-ingestion-resolve-Resolver-comparators) –
- [**discard_threshold**](#agrag-ingestion-resolve-Resolver-discard_threshold) –
- [**embedder**](#agrag-ingestion-resolve-Resolver-embedder) –
- [**hard_merge_threshold**](#agrag-ingestion-resolve-Resolver-hard_merge_threshold) –
- [**llm_batch_size**](#agrag-ingestion-resolve-Resolver-llm_batch_size) –
- [**max_llm_pairs**](#agrag-ingestion-resolve-Resolver-max_llm_pairs) –

**Parameters:**

- **comparators** (<code>list\[[Comparator](#agrag-ingestion-resolve-resolver-Comparator)\]</code>) – The ExactMatch, FuzzyMatch, and LLMVerify tiers,
  each picked out by type. A missing ExactMatch or FuzzyMatch
  falls back to its defaults; without an LLMVerify the LLM
  tier is skipped and boundary pairs never merge.
- **candidate_source** (<code>[CandidateSource](#agrag-ingestion-resolve-candidate_source-CandidateSource)</code>) – Narrows which pairs get compared at all.
- **embedder** (<code>[Embedder](embedding.md#agrag-embedding-base-Embedder) | None</code>) – Embeds mention texts for the similarity tier. None
  skips that tier: every fuzzy-uncertain pair counts as
  ambiguous, ranked by its fuzzy score.
- **hard_merge_threshold** (<code>float</code>) – Embedding similarity at or above which
  a pair merges without LLM review.
- **discard_threshold** (<code>float</code>) – Embedding similarity below which a pair
  drops without LLM review.
- **max_llm_pairs** (<code>int</code>) – Maximum ambiguous pairs sent to the LLM per
  label.
- **llm_batch_size** (<code>int</code>) – Pairs per LLM request. Must fit the
  LLMVerify comparator's max_pairs_per_batch.
- **tracer** (<code>Tracer | None</code>) – Opens this resolver's spans.

**Raises:**

- <code>ValueError</code> – llm_batch_size is not positive, or exceeds the
  LLMVerify comparator's max_pairs_per_batch.

##### `agrag.ingestion.resolve.Resolver.candidate_source` \{#agrag-ingestion-resolve-Resolver-candidate_source}

```python
candidate_source = candidate_source
```

##### `agrag.ingestion.resolve.Resolver.comparators` \{#agrag-ingestion-resolve-Resolver-comparators}

```python
comparators = comparators
```

##### `agrag.ingestion.resolve.Resolver.discard_threshold` \{#agrag-ingestion-resolve-Resolver-discard_threshold}

```python
discard_threshold = discard_threshold
```

##### `agrag.ingestion.resolve.Resolver.embedder` \{#agrag-ingestion-resolve-Resolver-embedder}

```python
embedder = embedder
```

##### `agrag.ingestion.resolve.Resolver.hard_merge_threshold` \{#agrag-ingestion-resolve-Resolver-hard_merge_threshold}

```python
hard_merge_threshold = hard_merge_threshold
```

##### `agrag.ingestion.resolve.Resolver.llm_batch_size` \{#agrag-ingestion-resolve-Resolver-llm_batch_size}

```python
llm_batch_size = llm_batch_size
```

##### `agrag.ingestion.resolve.Resolver.max_llm_pairs` \{#agrag-ingestion-resolve-Resolver-max_llm_pairs}

```python
max_llm_pairs = max_llm_pairs
```

##### `agrag.ingestion.resolve.Resolver.resolve` \{#agrag-ingestion-resolve-Resolver-resolve}

```python
resolve(entities:list[ExtractedEntity], *, neighbors_by_index:dict[int, list[str]] | None = None, similarity_by_pair:dict[tuple[int, int], float] | None = None) -> ResolutionResult
```

Resolve entity groups and retain each confirmed non-exact match.

**Parameters:**

- **entities** (<code>list\[[ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity)\]</code>) – The entities to resolve. Only entities passed in the
  same call are ever compared against each other — resolving
  against previously-resolved entities from an earlier call is
  not supported by this Resolver.
- **neighbors_by_index** (<code>dict\[int, list\[str\]\] | None</code>) – Entity index to that entity's neighboring-
  relationship context for LLM verification, when the caller has
  such a source. Omitted by callers that do not.
- **similarity_by_pair** (<code>dict\[tuple\[int, int\], float\] | None</code>) – Already-known real similarity scores keyed by
  `(min(left, right), max(left, right))`, such as an ANN
  backend's hit score. Never drives zone routing -- that scale
  is not comparable to this Resolver's own cosine similarity --
  but reaches the LLM as decision context, preferred over a
  freshly embedded score, for a pair that lands on the boundary
  anyway. Not mutated.

**Returns:**

- <code>[ResolutionResult](#agrag-ingestion-resolve-resolver-ResolutionResult)</code> – Groups for every input index, evidence for every confirmed
- <code>[ResolutionResult](#agrag-ingestion-resolve-resolver-ResolutionResult)</code> – non-exact pair, the count of uncertain LLM verdicts, and the
- <code>[ResolutionResult](#agrag-ingestion-resolve-resolver-ResolutionResult)</code> – counts of failed LLM requests and cap-truncated pairs.

#### `agrag.ingestion.resolve.batch_validation` \{#agrag-ingestion-resolve-batch_validation}

Validation for LLM batch entity-match verdicts.

**Classes:**

- [**BatchMatchVerdict**](#agrag-ingestion-resolve-batch_validation-BatchMatchVerdict) – One LLM result bound to the candidate pair it judged.

**Functions:**

- [**validate_batch_verdicts**](#agrag-ingestion-resolve-batch_validation-validate_batch_verdicts) – Return fail-safe verdicts keyed by requested candidate pair identifiers.

##### `agrag.ingestion.resolve.batch_validation.BatchMatchVerdict` \{#agrag-ingestion-resolve-batch_validation-BatchMatchVerdict}

Bases: <code>BaseModel</code>

One LLM result bound to the candidate pair it judged.

**Attributes:**

- [**pair_id**](#agrag-ingestion-resolve-batch_validation-BatchMatchVerdict-pair_id) (<code>str</code>) –
- [**reasoning**](#agrag-ingestion-resolve-batch_validation-BatchMatchVerdict-reasoning) (<code>str | None</code>) –
- [**verdict**](#agrag-ingestion-resolve-batch_validation-BatchMatchVerdict-verdict) (<code>[ComparisonVerdict](#agrag-ingestion-resolve-resolver-ComparisonVerdict)</code>) –

###### `agrag.ingestion.resolve.batch_validation.BatchMatchVerdict.pair_id` \{#agrag-ingestion-resolve-batch_validation-BatchMatchVerdict-pair_id}

```python
pair_id: str
```

###### `agrag.ingestion.resolve.batch_validation.BatchMatchVerdict.reasoning` \{#agrag-ingestion-resolve-batch_validation-BatchMatchVerdict-reasoning}

```python
reasoning: str | None = None
```

###### `agrag.ingestion.resolve.batch_validation.BatchMatchVerdict.verdict` \{#agrag-ingestion-resolve-batch_validation-BatchMatchVerdict-verdict}

```python
verdict: ComparisonVerdict
```

##### `agrag.ingestion.resolve.batch_validation.validate_batch_verdicts` \{#agrag-ingestion-resolve-batch_validation-validate_batch_verdicts}

```python
validate_batch_verdicts(pair_ids:Iterable[str], results:Iterable[object]) -> dict[str, ComparisonResult]
```

Return fail-safe verdicts keyed by requested candidate pair identifiers.

Unknown, duplicate, missing, and malformed results resolve to `NO_MATCH`.
This avoids assigning a valid LLM response to a different candidate pair.

#### `agrag.ingestion.resolve.build_relation_neighbors` \{#agrag-ingestion-resolve-build_relation_neighbors}

```python
build_relation_neighbors(entities:list[ExtractedEntity], relations:Sequence[ExtractedRelation], *, max_neighbors:int = MAX_NEIGHBORS_PER_ENTITY) -> dict[int, list[str]]
```

Build LLMVerify neighbor context from one batch's extracted relations.

**Parameters:**

- **entities** (<code>list\[[ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity)\]</code>) – The batch's mentions, indexed as `relations` references
  them.
- **relations** (<code>Sequence\[[ExtractedRelation](common.md#agrag-common-data_models-extraction-ExtractedRelation)\]</code>) – Relation mentions from the same extraction batch.
- **max_neighbors** (<code>int</code>) – Maximum neighbor strings kept per entity index.

**Returns:**

- <code>dict\[int, list\[str\]\]</code> – Entity index to a list of `"{relation_label} {other_entity_text}"`
- <code>dict\[int, list\[str\]\]</code> – strings, each direction of a relation contributing one entry to
- <code>dict\[int, list\[str\]\]</code> – both endpoints, capped at `max_neighbors` per index. An index with no
- <code>dict\[int, list\[str\]\]</code> – relation names has no key at all.

#### `agrag.ingestion.resolve.candidate_source` \{#agrag-ingestion-resolve-candidate_source}

Candidate generation for in-batch and persisted graph entities.

**Classes:**

- [**CandidateSource**](#agrag-ingestion-resolve-candidate_source-CandidateSource) – Narrows which in-batch entity pairs resolution compares.
- [**GraphCandidateSource**](#agrag-ingestion-resolve-candidate_source-GraphCandidateSource) – Blocks by label in-batch; ANN-searches persisted entities globally.
- [**PersistedCandidateSource**](#agrag-ingestion-resolve-candidate_source-PersistedCandidateSource) – Supplies only candidate pairs between new mentions and raw graph entities.

**Functions:**

- [**build_relation_neighbors**](#agrag-ingestion-resolve-candidate_source-build_relation_neighbors) – Build LLMVerify neighbor context from one batch's extracted relations.
- [**exact_match_lookup**](#agrag-ingestion-resolve-candidate_source-exact_match_lookup) – Return persisted exact matches, including accepted merge-key aliases.
- [**fetch_persisted_neighbors**](#agrag-ingestion-resolve-candidate_source-fetch_persisted_neighbors) – Fetch a bounded neighbor-relationship sample for persisted entities.
- [**persisted_candidate_indices**](#agrag-ingestion-resolve-candidate_source-persisted_candidate_indices) – Return ANN candidate indices, with a bounded exhaustive fallback.

**Attributes:**

- [**MAX_NEIGHBORS_PER_ENTITY**](#agrag-ingestion-resolve-candidate_source-MAX_NEIGHBORS_PER_ENTITY) –

##### `agrag.ingestion.resolve.candidate_source.CandidateSource` \{#agrag-ingestion-resolve-candidate_source-CandidateSource}

Bases: <code>ABC</code>

Narrows which in-batch entity pairs resolution compares.

**Functions:**

- [**candidates_for**](#agrag-ingestion-resolve-candidate_source-CandidateSource-candidates_for) – Return indices worth comparing against `entities[index]`.

###### `agrag.ingestion.resolve.candidate_source.CandidateSource.candidates_for` \{#agrag-ingestion-resolve-candidate_source-CandidateSource-candidates_for}

```python
candidates_for(index:int, entities:list[ExtractedEntity]) -> list[int]
```

Return indices worth comparing against `entities[index]`.

##### `agrag.ingestion.resolve.candidate_source.GraphCandidateSource` \{#agrag-ingestion-resolve-candidate_source-GraphCandidateSource}

```python
GraphCandidateSource(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, vector_collection:str = '', entity_labels:Sequence[str] = (), top_k:int = 50) -> None
```

Bases: <code>[CandidateSource](#agrag-ingestion-resolve-candidate_source-CandidateSource)</code>

Blocks by label in-batch; ANN-searches persisted entities globally.

**Functions:**

- [**candidates_for**](#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-candidates_for) – Return every other mention sharing the indexed mention's label.
- [**global_candidates_for**](#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-global_candidates_for) – Return persisted entities found by the shared vector-search route.

**Attributes:**

- [**embedder**](#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-embedder) –
- [**entity_labels**](#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-entity_labels) –
- [**graph_store**](#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-graph_store) –
- [**top_k**](#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-top_k) –
- [**vector_collection**](#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-vector_collection) –
- [**vector_store**](#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-vector_store) –

###### `agrag.ingestion.resolve.candidate_source.GraphCandidateSource.candidates_for` \{#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-candidates_for}

```python
candidates_for(index:int, entities:list[ExtractedEntity]) -> list[int]
```

Return every other mention sharing the indexed mention's label.

###### `agrag.ingestion.resolve.candidate_source.GraphCandidateSource.embedder` \{#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-embedder}

```python
embedder = embedder
```

###### `agrag.ingestion.resolve.candidate_source.GraphCandidateSource.entity_labels` \{#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-entity_labels}

```python
entity_labels = tuple(entity_labels)
```

###### `agrag.ingestion.resolve.candidate_source.GraphCandidateSource.global_candidates_for` \{#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-global_candidates_for}

```python
global_candidates_for(mention:ExtractedEntity) -> list[tuple[Entity, float]]
```

Return persisted entities found by the shared vector-search route.

The GraphStore-native path's payload already carries the real node
properties and is validated directly. The VectorStore path's payload
only carries `label` and `text` (the embedding source text), so
candidates are loaded from the graph by hit id instead; a hit that
fails to load, for example a deleted node, is
skipped rather than reconstructed from `text`.

Each candidate is paired with the cosine similarity of the
`VectorHit` it came from. The association is keyed by hit id, never
by position: either branch can drop an entity (malformed payload,
label mismatch, failed load) without dropping the corresponding
score, so zipping the two lists positionally would silently shift
scores onto the wrong entities.

**Returns:**

- <code>list\[tuple\[[Entity](common.md#agrag-common-data_models-entity-Entity), float\]\]</code> – `(Entity, score)` pairs in hit order. `score` is `0.0` for
- <code>list\[tuple\[[Entity](common.md#agrag-common-data_models-entity-Entity), float\]\]</code> – an entity whose id is absent from the hit map, which should not
- <code>list\[tuple\[[Entity](common.md#agrag-common-data_models-entity-Entity), float\]\]</code> – happen since candidate ids come from those same hits.

###### `agrag.ingestion.resolve.candidate_source.GraphCandidateSource.graph_store` \{#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-graph_store}

```python
graph_store = graph_store
```

###### `agrag.ingestion.resolve.candidate_source.GraphCandidateSource.top_k` \{#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-top_k}

```python
top_k = top_k
```

###### `agrag.ingestion.resolve.candidate_source.GraphCandidateSource.vector_collection` \{#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-vector_collection}

```python
vector_collection = vector_collection
```

###### `agrag.ingestion.resolve.candidate_source.GraphCandidateSource.vector_store` \{#agrag-ingestion-resolve-candidate_source-GraphCandidateSource-vector_store}

```python
vector_store = vector_store
```

##### `agrag.ingestion.resolve.candidate_source.MAX_NEIGHBORS_PER_ENTITY` \{#agrag-ingestion-resolve-candidate_source-MAX_NEIGHBORS_PER_ENTITY}

```python
MAX_NEIGHBORS_PER_ENTITY = 5
```

##### `agrag.ingestion.resolve.candidate_source.PersistedCandidateSource` \{#agrag-ingestion-resolve-candidate_source-PersistedCandidateSource}

```python
PersistedCandidateSource(candidates_by_index:dict[int, list[int]]) -> None
```

Bases: <code>[CandidateSource](#agrag-ingestion-resolve-candidate_source-CandidateSource)</code>

Supplies only candidate pairs between new mentions and raw graph entities.

**Functions:**

- [**candidates_for**](#agrag-ingestion-resolve-candidate_source-PersistedCandidateSource-candidates_for) – Return persisted candidates for a newly extracted mention.

**Attributes:**

- [**candidates_by_index**](#agrag-ingestion-resolve-candidate_source-PersistedCandidateSource-candidates_by_index) –

###### `agrag.ingestion.resolve.candidate_source.PersistedCandidateSource.candidates_by_index` \{#agrag-ingestion-resolve-candidate_source-PersistedCandidateSource-candidates_by_index}

```python
candidates_by_index = candidates_by_index
```

###### `agrag.ingestion.resolve.candidate_source.PersistedCandidateSource.candidates_for` \{#agrag-ingestion-resolve-candidate_source-PersistedCandidateSource-candidates_for}

```python
candidates_for(index:int, entities:list[ExtractedEntity]) -> list[int]
```

Return persisted candidates for a newly extracted mention.

##### `agrag.ingestion.resolve.candidate_source.build_relation_neighbors` \{#agrag-ingestion-resolve-candidate_source-build_relation_neighbors}

```python
build_relation_neighbors(entities:list[ExtractedEntity], relations:Sequence[ExtractedRelation], *, max_neighbors:int = MAX_NEIGHBORS_PER_ENTITY) -> dict[int, list[str]]
```

Build LLMVerify neighbor context from one batch's extracted relations.

**Parameters:**

- **entities** (<code>list\[[ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity)\]</code>) – The batch's mentions, indexed as `relations` references
  them.
- **relations** (<code>Sequence\[[ExtractedRelation](common.md#agrag-common-data_models-extraction-ExtractedRelation)\]</code>) – Relation mentions from the same extraction batch.
- **max_neighbors** (<code>int</code>) – Maximum neighbor strings kept per entity index.

**Returns:**

- <code>dict\[int, list\[str\]\]</code> – Entity index to a list of `"{relation_label} {other_entity_text}"`
- <code>dict\[int, list\[str\]\]</code> – strings, each direction of a relation contributing one entry to
- <code>dict\[int, list\[str\]\]</code> – both endpoints, capped at `max_neighbors` per index. An index with no
- <code>dict\[int, list\[str\]\]</code> – relation names has no key at all.

##### `agrag.ingestion.resolve.candidate_source.exact_match_lookup` \{#agrag-ingestion-resolve-candidate_source-exact_match_lookup}

```python
exact_match_lookup(mentions:list[ExtractedEntity], *, graph_store:GraphStore) -> dict[int, Entity]
```

Return persisted exact matches, including accepted merge-key aliases.

##### `agrag.ingestion.resolve.candidate_source.fetch_persisted_neighbors` \{#agrag-ingestion-resolve-candidate_source-fetch_persisted_neighbors}

```python
fetch_persisted_neighbors(entity_ids:Sequence[UUID], *, graph_store:GraphStore, exclude_relation_types:Sequence[str], max_neighbors:int = MAX_NEIGHBORS_PER_ENTITY) -> dict[UUID, list[str]]
```

Fetch a bounded neighbor-relationship sample for persisted entities.

**Parameters:**

- **entity_ids** (<code>Sequence\[UUID\]</code>) – Persisted entity ids to fetch neighbors for.
- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Store to read from.
- **exclude_relation_types** (<code>Sequence\[str\]</code>) – Relation types to omit, such as resolution's
  own system relation types (`MATCHES`, `RESOLVED_AS`, etc.) —
  passed by the caller rather than imported here, since importing
  `agrag.ingestion.graph`'s `SYSTEM_RELATION_TYPES` into this
  module would invert the existing import direction
  (`graph.py` already imports from this module).
- **max_neighbors** (<code>int</code>) – Maximum neighbor strings kept per entity id.

**Returns:**

- <code>dict\[UUID, list\[str\]\]</code> – Entity id to a list of `"{rel_type} {neighbor_name}"` strings. An
- <code>dict\[UUID, list\[str\]\]</code> – id with no matching relations, and a malformed row, contribute
- <code>dict\[UUID, list\[str\]\]</code> – nothing, so that id is simply absent from the map — every caller
- <code>dict\[UUID, list\[str\]\]</code> – reads through `.get(id, [])`.

##### `agrag.ingestion.resolve.candidate_source.persisted_candidate_indices` \{#agrag-ingestion-resolve-candidate_source-persisted_candidate_indices}

```python
persisted_candidate_indices(mentions:list[ExtractedEntity], entities:list[Entity], *, source:GraphCandidateSource, fallback_limit:int = 128) -> tuple[dict[int, list[int]], dict[tuple[int, int], float]]
```

Return ANN candidate indices, with a bounded exhaustive fallback.

The fallback only applies when no indexed candidates are available. It
keeps first-time and small-graph consolidation deterministic without
returning to an unbounded pairwise scan for established graphs.

**Returns:**

- <code>dict\[int, list\[int\]\]</code> – Mention index to its candidate entity indices, plus each compared
- <code>dict\[tuple\[int, int\], float\]</code> – pair's real embedding cosine similarity keyed by `(min, max)`
- <code>tuple\[dict\[int, list\[int\]\], dict\[tuple\[int, int\], float\]\]</code> – index order (matching how `Resolver.resolve` builds its own pair
- <code>tuple\[dict\[int, list\[int\]\], dict\[tuple\[int, int\], float\]\]</code> – keys). The exhaustive-fallback branch reports no scores, so its
- <code>tuple\[dict\[int, list\[int\]\], dict\[tuple\[int, int\], float\]\]</code> – similarity map is empty.

#### `agrag.ingestion.resolve.comparators` \{#agrag-ingestion-resolve-comparators}

Comparison strategies used by entity resolution.

**Classes:**

- [**Comparator**](#agrag-ingestion-resolve-comparators-Comparator) – One matching strategy a Resolver runs against a candidate pair.
- [**ComparisonResult**](#agrag-ingestion-resolve-comparators-ComparisonResult) – The verdict and evidence produced by one comparator.
- [**ComparisonVerdict**](#agrag-ingestion-resolve-comparators-ComparisonVerdict) – A Comparator's verdict on one entity pair.
- [**ExactMatch**](#agrag-ingestion-resolve-comparators-ExactMatch) – Matches when normalized text is identical. Never returns NO_MATCH.
- [**FuzzyMatch**](#agrag-ingestion-resolve-comparators-FuzzyMatch) – Fast-path accepter for near-identical names. Never returns NO_MATCH.
- [**LLMVerify**](#agrag-ingestion-resolve-comparators-LLMVerify) – Asks an LLM to verify an ambiguous pair. Last resort; never UNCERTAIN.

##### `agrag.ingestion.resolve.comparators.Comparator` \{#agrag-ingestion-resolve-comparators-Comparator}

Bases: <code>ABC</code>

One matching strategy a Resolver runs against a candidate pair.

**Functions:**

- [**compare**](#agrag-ingestion-resolve-comparators-Comparator-compare) – Compare two entities.
- [**compare_with_evidence**](#agrag-ingestion-resolve-comparators-Comparator-compare_with_evidence) – Compare two entities and retain any available decision evidence.

###### `agrag.ingestion.resolve.comparators.Comparator.compare` \{#agrag-ingestion-resolve-comparators-Comparator-compare}

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Compare two entities.

**Parameters:**

- **a** (<code>[ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity)</code>) – The first entity.
- **b** (<code>[ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity)</code>) – The second entity.

**Returns:**

- <code>[ComparisonVerdict](#agrag-ingestion-resolve-resolver-ComparisonVerdict)</code> – This comparator's verdict. UNCERTAIN defers to the next comparator.

###### `agrag.ingestion.resolve.comparators.Comparator.compare_with_evidence` \{#agrag-ingestion-resolve-comparators-Comparator-compare_with_evidence}

```python
compare_with_evidence(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonResult
```

Compare two entities and retain any available decision evidence.

##### `agrag.ingestion.resolve.comparators.ComparisonResult` \{#agrag-ingestion-resolve-comparators-ComparisonResult}

Bases: <code>BaseModel</code>

The verdict and evidence produced by one comparator.

**Attributes:**

- [**reasoning**](#agrag-ingestion-resolve-comparators-ComparisonResult-reasoning) (<code>str | None</code>) –
- [**score**](#agrag-ingestion-resolve-comparators-ComparisonResult-score) (<code>float | None</code>) –
- [**verdict**](#agrag-ingestion-resolve-comparators-ComparisonResult-verdict) (<code>[ComparisonVerdict](#agrag-ingestion-resolve-resolver-ComparisonVerdict)</code>) –

###### `agrag.ingestion.resolve.comparators.ComparisonResult.reasoning` \{#agrag-ingestion-resolve-comparators-ComparisonResult-reasoning}

```python
reasoning: str | None = None
```

###### `agrag.ingestion.resolve.comparators.ComparisonResult.score` \{#agrag-ingestion-resolve-comparators-ComparisonResult-score}

```python
score: float | None = None
```

###### `agrag.ingestion.resolve.comparators.ComparisonResult.verdict` \{#agrag-ingestion-resolve-comparators-ComparisonResult-verdict}

```python
verdict: ComparisonVerdict
```

##### `agrag.ingestion.resolve.comparators.ComparisonVerdict` \{#agrag-ingestion-resolve-comparators-ComparisonVerdict}

Bases: <code>StrEnum</code>

A Comparator's verdict on one entity pair.

**Attributes:**

- [**MATCH**](#agrag-ingestion-resolve-comparators-ComparisonVerdict-MATCH) – The comparator is confident these are the same entity.
- [**NO_MATCH**](#agrag-ingestion-resolve-comparators-ComparisonVerdict-NO_MATCH) – The comparator is confident these are different entities.
- [**UNCERTAIN**](#agrag-ingestion-resolve-comparators-ComparisonVerdict-UNCERTAIN) – This comparator can't decide; the next one gets a turn.

###### `agrag.ingestion.resolve.comparators.ComparisonVerdict.MATCH` \{#agrag-ingestion-resolve-comparators-ComparisonVerdict-MATCH}

```python
MATCH = 'match'
```

###### `agrag.ingestion.resolve.comparators.ComparisonVerdict.NO_MATCH` \{#agrag-ingestion-resolve-comparators-ComparisonVerdict-NO_MATCH}

```python
NO_MATCH = 'no_match'
```

###### `agrag.ingestion.resolve.comparators.ComparisonVerdict.UNCERTAIN` \{#agrag-ingestion-resolve-comparators-ComparisonVerdict-UNCERTAIN}

```python
UNCERTAIN = 'uncertain'
```

##### `agrag.ingestion.resolve.comparators.ExactMatch` \{#agrag-ingestion-resolve-comparators-ExactMatch}

Bases: <code>[Comparator](#agrag-ingestion-resolve-resolver-Comparator)</code>

Matches when normalized text is identical. Never returns NO_MATCH.

**Functions:**

- [**compare**](#agrag-ingestion-resolve-comparators-ExactMatch-compare) – Return MATCH on identical normalized text, else UNCERTAIN.
- [**compare_with_evidence**](#agrag-ingestion-resolve-comparators-ExactMatch-compare_with_evidence) – Compare two entities and retain any available decision evidence.

###### `agrag.ingestion.resolve.comparators.ExactMatch.compare` \{#agrag-ingestion-resolve-comparators-ExactMatch-compare}

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Return MATCH on identical normalized text, else UNCERTAIN.

###### `agrag.ingestion.resolve.comparators.ExactMatch.compare_with_evidence` \{#agrag-ingestion-resolve-comparators-ExactMatch-compare_with_evidence}

```python
compare_with_evidence(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonResult
```

Compare two entities and retain any available decision evidence.

##### `agrag.ingestion.resolve.comparators.FuzzyMatch` \{#agrag-ingestion-resolve-comparators-FuzzyMatch}

```python
FuzzyMatch(*, match_above:float = 0.97) -> None
```

Bases: <code>[Comparator](#agrag-ingestion-resolve-resolver-Comparator)</code>

Fast-path accepter for near-identical names. Never returns NO_MATCH.

Rejection belongs to later tiers, which see embedding and LLM evidence
this comparator lacks.

**Attributes:**

- [**match_above**](#agrag-ingestion-resolve-comparators-FuzzyMatch-match_above) – A similarity score at or above this is a match.

**Functions:**

- [**compare**](#agrag-ingestion-resolve-comparators-FuzzyMatch-compare) – Return a verdict from token-sort-ratio similarity.
- [**compare_with_evidence**](#agrag-ingestion-resolve-comparators-FuzzyMatch-compare_with_evidence) – Compare two entities and include their token-sort similarity.

###### `agrag.ingestion.resolve.comparators.FuzzyMatch.compare` \{#agrag-ingestion-resolve-comparators-FuzzyMatch-compare}

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Return a verdict from token-sort-ratio similarity.

###### `agrag.ingestion.resolve.comparators.FuzzyMatch.compare_with_evidence` \{#agrag-ingestion-resolve-comparators-FuzzyMatch-compare_with_evidence}

```python
compare_with_evidence(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonResult
```

Compare two entities and include their token-sort similarity.

###### `agrag.ingestion.resolve.comparators.FuzzyMatch.match_above` \{#agrag-ingestion-resolve-comparators-FuzzyMatch-match_above}

```python
match_above = match_above
```

##### `agrag.ingestion.resolve.comparators.LLMVerify` \{#agrag-ingestion-resolve-comparators-LLMVerify}

```python
LLMVerify(*, chunks_by_id:dict[UUID, Chunk], settings:ExtractionLLMSettings | None = None, client:object | None = None, max_pairs_per_batch:int = 50, tracer:Tracer | None = None) -> None
```

Bases: <code>[Comparator](#agrag-ingestion-resolve-resolver-Comparator)</code>

Asks an LLM to verify an ambiguous pair. Last resort; never UNCERTAIN.

Never raises from an LLM-call failure: it resolves to NO_MATCH instead, by
the same fail-safe design as every comparator a Resolver runs — an
ambiguous or failed comparison never merges two entities. A missing package
extra is a configuration error, not an ambiguous judgment call, and is
raised outright instead (see compare's Raises section).

**Functions:**

- [**compare**](#agrag-ingestion-resolve-comparators-LLMVerify-compare) – Return the LLM's verdict for one pair, or NO_MATCH on failure.
- [**compare_batch**](#agrag-ingestion-resolve-comparators-LLMVerify-compare_batch) – Verify ambiguous candidate pairs across bounded LLM requests.
- [**compare_batch_detailed**](#agrag-ingestion-resolve-comparators-LLMVerify-compare_batch_detailed) – Verify pairs and count how many verdicts came back uncertain.
- [**compare_with_evidence**](#agrag-ingestion-resolve-comparators-LLMVerify-compare_with_evidence) – Compare two entities and retain any available decision evidence.

**Attributes:**

- [**chunks_by_id**](#agrag-ingestion-resolve-comparators-LLMVerify-chunks_by_id) –
- [**failed_requests**](#agrag-ingestion-resolve-comparators-LLMVerify-failed_requests) (<code>int</code>) –
- [**max_pairs_per_batch**](#agrag-ingestion-resolve-comparators-LLMVerify-max_pairs_per_batch) –
- [**settings**](#agrag-ingestion-resolve-comparators-LLMVerify-settings) –

**Parameters:**

- **chunks_by_id** (<code>dict\[UUID, [Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code>) – Maps a Chunk id to the Chunk, for prompt context.
- **settings** (<code>[ExtractionLLMSettings](#agrag-ingestion-extract-ExtractionLLMSettings) | None</code>) – LLM client config. Defaults to `ExtractionLLMSettings()`.
  Ignored when `client` is given: an injected client also
  disables `settings.retry`, since a caller building its own
  client is assumed to own its own retry behavior too.
- **client** (<code>object | None</code>) – An already-built BAML client. Tests inject a fake here.
- **max_pairs_per_batch** (<code>int</code>) – Maximum pairs sent to the LLM in one request.
  A large ambiguous population is split into requests of at most
  this size so one oversized request cannot exceed the model's
  context limit and silently fail every pair in the batch.
- **tracer** (<code>Tracer | None</code>) – Opens the `agrag.resolution.llm_verify` span and the
  LLM call spans below it.

###### `agrag.ingestion.resolve.comparators.LLMVerify.chunks_by_id` \{#agrag-ingestion-resolve-comparators-LLMVerify-chunks_by_id}

```python
chunks_by_id = chunks_by_id
```

###### `agrag.ingestion.resolve.comparators.LLMVerify.compare` \{#agrag-ingestion-resolve-comparators-LLMVerify-compare}

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Return the LLM's verdict for one pair, or NO_MATCH on failure.

Runs through compare_batch so the single-pair path shares the
batch validation and fail-safe behavior.

**Raises:**

- <code>[ExtractorMissingExtraError](#agrag-ingestion-extract-ExtractorMissingExtraError)</code> – The `llm` package extra is not
  installed.

###### `agrag.ingestion.resolve.comparators.LLMVerify.compare_batch` \{#agrag-ingestion-resolve-comparators-LLMVerify-compare_batch}

```python
compare_batch(pairs:list[tuple[int, int, ExtractedEntity, ExtractedEntity]], *, similarities:dict[tuple[int, int], float] | None = None, neighbors_by_index:dict[int, list[str]] | None = None) -> dict[tuple[int, int], ComparisonResult]
```

Verify ambiguous candidate pairs across bounded LLM requests.

Splits into requests of at most `max_pairs_per_batch` pairs so one
oversized population cannot exceed the model's context limit.
Invalid, missing, and uncertain model responses do not merge entities.

**Parameters:**

- **pairs** (<code>list\[tuple\[int, int, [ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity), [ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity)\]\]</code>) – `(left_index, right_index, left, right)` tuples to verify.
- **similarities** (<code>dict\[tuple\[int, int\], float\] | None</code>) – Embedding similarity per pair, sent to the model
  as decision context. Defaults to 0.0 when unknown.
- **neighbors_by_index** (<code>dict\[int, list\[str\]\] | None</code>) – Entity index to its neighboring-relationship
  context strings. Looked up globally, so every chunk sees the
  same map.

###### `agrag.ingestion.resolve.comparators.LLMVerify.compare_batch_detailed` \{#agrag-ingestion-resolve-comparators-LLMVerify-compare_batch_detailed}

```python
compare_batch_detailed(pairs:list[tuple[int, int, ExtractedEntity, ExtractedEntity]], *, similarities:dict[tuple[int, int], float] | None = None, neighbors_by_index:dict[int, list[str]] | None = None) -> tuple[dict[tuple[int, int], ComparisonResult], int]
```

Verify pairs and count how many verdicts came back uncertain.

**Parameters:**

- **pairs** (<code>list\[tuple\[int, int, [ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity), [ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity)\]\]</code>) – The candidate pairs to verify.
- **similarities** (<code>dict\[tuple\[int, int\], float\] | None</code>) – Embedding similarity per pair, sent to the model
  as decision context. Defaults to 0.0 when unknown.
- **neighbors_by_index** (<code>dict\[int, list\[str\]\] | None</code>) – Entity index to its neighboring-relationship
  context strings. Looked up globally, so every chunk sees the
  same map.

**Returns:**

- <code>dict\[tuple\[int, int\], [ComparisonResult](#agrag-ingestion-resolve-resolver-ComparisonResult)\]</code> – The per-pair results and the count of raw uncertain verdicts,
- <code>int</code> – before the fail-safe maps them to NO_MATCH. A request that
- <code>tuple\[dict\[tuple\[int, int\], [ComparisonResult](#agrag-ingestion-resolve-resolver-ComparisonResult)\], int\]</code> – errors maps its pairs to NO_MATCH and increments
- <code>tuple\[dict\[tuple\[int, int\], [ComparisonResult](#agrag-ingestion-resolve-resolver-ComparisonResult)\], int\]</code> – failed_requests.

###### `agrag.ingestion.resolve.comparators.LLMVerify.compare_with_evidence` \{#agrag-ingestion-resolve-comparators-LLMVerify-compare_with_evidence}

```python
compare_with_evidence(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonResult
```

Compare two entities and retain any available decision evidence.

###### `agrag.ingestion.resolve.comparators.LLMVerify.failed_requests` \{#agrag-ingestion-resolve-comparators-LLMVerify-failed_requests}

```python
failed_requests: int = 0
```

###### `agrag.ingestion.resolve.comparators.LLMVerify.max_pairs_per_batch` \{#agrag-ingestion-resolve-comparators-LLMVerify-max_pairs_per_batch}

```python
max_pairs_per_batch = max_pairs_per_batch
```

###### `agrag.ingestion.resolve.comparators.LLMVerify.settings` \{#agrag-ingestion-resolve-comparators-LLMVerify-settings}

```python
settings = settings
```

#### `agrag.ingestion.resolve.exact_groups` \{#agrag-ingestion-resolve-exact_groups}

Exact-name grouping for permanent raw entity records.

**Functions:**

- [**exact_resolution_groups**](#agrag-ingestion-resolve-exact_groups-exact_resolution_groups) – Group mentions only when they share exact raw-entity identity.

##### `agrag.ingestion.resolve.exact_groups.exact_resolution_groups` \{#agrag-ingestion-resolve-exact_groups-exact_resolution_groups}

```python
exact_resolution_groups(mentions:list[ExtractedEntity], exact_matches:dict[int, Entity]) -> list[ResolutionGroup]
```

Group mentions only when they share exact raw-entity identity.

A mention with a persisted exact match joins every other mention that
resolves to the same raw Entity. Other mentions join only when their
labels and normalized names match. Semantic matches deliberately remain
separate raw records and become resolved entities through `MATCHES` later.

#### `agrag.ingestion.resolve.exact_match_lookup` \{#agrag-ingestion-resolve-exact_match_lookup}

```python
exact_match_lookup(mentions:list[ExtractedEntity], *, graph_store:GraphStore) -> dict[int, Entity]
```

Return persisted exact matches, including accepted merge-key aliases.

#### `agrag.ingestion.resolve.exact_resolution_groups` \{#agrag-ingestion-resolve-exact_resolution_groups}

```python
exact_resolution_groups(mentions:list[ExtractedEntity], exact_matches:dict[int, Entity]) -> list[ResolutionGroup]
```

Group mentions only when they share exact raw-entity identity.

A mention with a persisted exact match joins every other mention that
resolves to the same raw Entity. Other mentions join only when their
labels and normalized names match. Semantic matches deliberately remain
separate raw records and become resolved entities through `MATCHES` later.

#### `agrag.ingestion.resolve.fetch_persisted_neighbors` \{#agrag-ingestion-resolve-fetch_persisted_neighbors}

```python
fetch_persisted_neighbors(entity_ids:Sequence[UUID], *, graph_store:GraphStore, exclude_relation_types:Sequence[str], max_neighbors:int = MAX_NEIGHBORS_PER_ENTITY) -> dict[UUID, list[str]]
```

Fetch a bounded neighbor-relationship sample for persisted entities.

**Parameters:**

- **entity_ids** (<code>Sequence\[UUID\]</code>) – Persisted entity ids to fetch neighbors for.
- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Store to read from.
- **exclude_relation_types** (<code>Sequence\[str\]</code>) – Relation types to omit, such as resolution's
  own system relation types (`MATCHES`, `RESOLVED_AS`, etc.) —
  passed by the caller rather than imported here, since importing
  `agrag.ingestion.graph`'s `SYSTEM_RELATION_TYPES` into this
  module would invert the existing import direction
  (`graph.py` already imports from this module).
- **max_neighbors** (<code>int</code>) – Maximum neighbor strings kept per entity id.

**Returns:**

- <code>dict\[UUID, list\[str\]\]</code> – Entity id to a list of `"{rel_type} {neighbor_name}"` strings. An
- <code>dict\[UUID, list\[str\]\]</code> – id with no matching relations, and a malformed row, contribute
- <code>dict\[UUID, list\[str\]\]</code> – nothing, so that id is simply absent from the map — every caller
- <code>dict\[UUID, list\[str\]\]</code> – reads through `.get(id, [])`.

#### `agrag.ingestion.resolve.persisted_candidate_indices` \{#agrag-ingestion-resolve-persisted_candidate_indices}

```python
persisted_candidate_indices(mentions:list[ExtractedEntity], entities:list[Entity], *, source:GraphCandidateSource, fallback_limit:int = 128) -> tuple[dict[int, list[int]], dict[tuple[int, int], float]]
```

Return ANN candidate indices, with a bounded exhaustive fallback.

The fallback only applies when no indexed candidates are available. It
keeps first-time and small-graph consolidation deterministic without
returning to an unbounded pairwise scan for established graphs.

**Returns:**

- <code>dict\[int, list\[int\]\]</code> – Mention index to its candidate entity indices, plus each compared
- <code>dict\[tuple\[int, int\], float\]</code> – pair's real embedding cosine similarity keyed by `(min, max)`
- <code>tuple\[dict\[int, list\[int\]\], dict\[tuple\[int, int\], float\]\]</code> – index order (matching how `Resolver.resolve` builds its own pair
- <code>tuple\[dict\[int, list\[int\]\], dict\[tuple\[int, int\], float\]\]</code> – keys). The exhaustive-fallback branch reports no scores, so its
- <code>tuple\[dict\[int, list\[int\]\], dict\[tuple\[int, int\], float\]\]</code> – similarity map is empty.

#### `agrag.ingestion.resolve.resolver` \{#agrag-ingestion-resolve-resolver}

Entity resolution: deciding which ExtractedEntity mentions are the same thing.

**Classes:**

- [**Comparator**](#agrag-ingestion-resolve-resolver-Comparator) – One matching strategy a Resolver runs against a candidate pair.
- [**ComparisonResult**](#agrag-ingestion-resolve-resolver-ComparisonResult) – The verdict and evidence produced by one comparator.
- [**ComparisonVerdict**](#agrag-ingestion-resolve-resolver-ComparisonVerdict) – A Comparator's verdict on one entity pair.
- [**ExactMatch**](#agrag-ingestion-resolve-resolver-ExactMatch) – Matches when normalized text is identical. Never returns NO_MATCH.
- [**FuzzyMatch**](#agrag-ingestion-resolve-resolver-FuzzyMatch) – Fast-path accepter for near-identical names. Never returns NO_MATCH.
- [**LLMVerify**](#agrag-ingestion-resolve-resolver-LLMVerify) – Asks an LLM to verify an ambiguous pair. Last resort; never UNCERTAIN.
- [**ResolutionGroup**](#agrag-ingestion-resolve-resolver-ResolutionGroup) – One set of ExtractedEntity indices resolution decided are the same entity.
- [**ResolutionResult**](#agrag-ingestion-resolve-resolver-ResolutionResult) – The groups, non-exact evidence, and ambiguity count of one pass.
- [**ResolvedMatch**](#agrag-ingestion-resolve-resolver-ResolvedMatch) – One confirmed non-exact match between two input entity indices.
- [**Resolver**](#agrag-ingestion-resolve-resolver-Resolver) – Routes blocked candidate pairs through exact, fuzzy, embedding, and LLM zones.

**Attributes:**

- [**logger**](#agrag-ingestion-resolve-resolver-logger) –

##### `agrag.ingestion.resolve.resolver.Comparator` \{#agrag-ingestion-resolve-resolver-Comparator}

Bases: <code>ABC</code>

One matching strategy a Resolver runs against a candidate pair.

**Functions:**

- [**compare**](#agrag-ingestion-resolve-resolver-Comparator-compare) – Compare two entities.
- [**compare_with_evidence**](#agrag-ingestion-resolve-resolver-Comparator-compare_with_evidence) – Compare two entities and retain any available decision evidence.

###### `agrag.ingestion.resolve.resolver.Comparator.compare` \{#agrag-ingestion-resolve-resolver-Comparator-compare}

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Compare two entities.

**Parameters:**

- **a** (<code>[ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity)</code>) – The first entity.
- **b** (<code>[ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity)</code>) – The second entity.

**Returns:**

- <code>[ComparisonVerdict](#agrag-ingestion-resolve-resolver-ComparisonVerdict)</code> – This comparator's verdict. UNCERTAIN defers to the next comparator.

###### `agrag.ingestion.resolve.resolver.Comparator.compare_with_evidence` \{#agrag-ingestion-resolve-resolver-Comparator-compare_with_evidence}

```python
compare_with_evidence(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonResult
```

Compare two entities and retain any available decision evidence.

##### `agrag.ingestion.resolve.resolver.ComparisonResult` \{#agrag-ingestion-resolve-resolver-ComparisonResult}

Bases: <code>BaseModel</code>

The verdict and evidence produced by one comparator.

**Attributes:**

- [**reasoning**](#agrag-ingestion-resolve-resolver-ComparisonResult-reasoning) (<code>str | None</code>) –
- [**score**](#agrag-ingestion-resolve-resolver-ComparisonResult-score) (<code>float | None</code>) –
- [**verdict**](#agrag-ingestion-resolve-resolver-ComparisonResult-verdict) (<code>[ComparisonVerdict](#agrag-ingestion-resolve-resolver-ComparisonVerdict)</code>) –

###### `agrag.ingestion.resolve.resolver.ComparisonResult.reasoning` \{#agrag-ingestion-resolve-resolver-ComparisonResult-reasoning}

```python
reasoning: str | None = None
```

###### `agrag.ingestion.resolve.resolver.ComparisonResult.score` \{#agrag-ingestion-resolve-resolver-ComparisonResult-score}

```python
score: float | None = None
```

###### `agrag.ingestion.resolve.resolver.ComparisonResult.verdict` \{#agrag-ingestion-resolve-resolver-ComparisonResult-verdict}

```python
verdict: ComparisonVerdict
```

##### `agrag.ingestion.resolve.resolver.ComparisonVerdict` \{#agrag-ingestion-resolve-resolver-ComparisonVerdict}

Bases: <code>StrEnum</code>

A Comparator's verdict on one entity pair.

**Attributes:**

- [**MATCH**](#agrag-ingestion-resolve-resolver-ComparisonVerdict-MATCH) – The comparator is confident these are the same entity.
- [**NO_MATCH**](#agrag-ingestion-resolve-resolver-ComparisonVerdict-NO_MATCH) – The comparator is confident these are different entities.
- [**UNCERTAIN**](#agrag-ingestion-resolve-resolver-ComparisonVerdict-UNCERTAIN) – This comparator can't decide; the next one gets a turn.

###### `agrag.ingestion.resolve.resolver.ComparisonVerdict.MATCH` \{#agrag-ingestion-resolve-resolver-ComparisonVerdict-MATCH}

```python
MATCH = 'match'
```

###### `agrag.ingestion.resolve.resolver.ComparisonVerdict.NO_MATCH` \{#agrag-ingestion-resolve-resolver-ComparisonVerdict-NO_MATCH}

```python
NO_MATCH = 'no_match'
```

###### `agrag.ingestion.resolve.resolver.ComparisonVerdict.UNCERTAIN` \{#agrag-ingestion-resolve-resolver-ComparisonVerdict-UNCERTAIN}

```python
UNCERTAIN = 'uncertain'
```

##### `agrag.ingestion.resolve.resolver.ExactMatch` \{#agrag-ingestion-resolve-resolver-ExactMatch}

Bases: <code>[Comparator](#agrag-ingestion-resolve-resolver-Comparator)</code>

Matches when normalized text is identical. Never returns NO_MATCH.

**Functions:**

- [**compare**](#agrag-ingestion-resolve-resolver-ExactMatch-compare) – Return MATCH on identical normalized text, else UNCERTAIN.
- [**compare_with_evidence**](#agrag-ingestion-resolve-resolver-ExactMatch-compare_with_evidence) – Compare two entities and retain any available decision evidence.

###### `agrag.ingestion.resolve.resolver.ExactMatch.compare` \{#agrag-ingestion-resolve-resolver-ExactMatch-compare}

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Return MATCH on identical normalized text, else UNCERTAIN.

###### `agrag.ingestion.resolve.resolver.ExactMatch.compare_with_evidence` \{#agrag-ingestion-resolve-resolver-ExactMatch-compare_with_evidence}

```python
compare_with_evidence(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonResult
```

Compare two entities and retain any available decision evidence.

##### `agrag.ingestion.resolve.resolver.FuzzyMatch` \{#agrag-ingestion-resolve-resolver-FuzzyMatch}

```python
FuzzyMatch(*, match_above:float = 0.97) -> None
```

Bases: <code>[Comparator](#agrag-ingestion-resolve-resolver-Comparator)</code>

Fast-path accepter for near-identical names. Never returns NO_MATCH.

Rejection belongs to later tiers, which see embedding and LLM evidence
this comparator lacks.

**Attributes:**

- [**match_above**](#agrag-ingestion-resolve-resolver-FuzzyMatch-match_above) – A similarity score at or above this is a match.

**Functions:**

- [**compare**](#agrag-ingestion-resolve-resolver-FuzzyMatch-compare) – Return a verdict from token-sort-ratio similarity.
- [**compare_with_evidence**](#agrag-ingestion-resolve-resolver-FuzzyMatch-compare_with_evidence) – Compare two entities and include their token-sort similarity.

###### `agrag.ingestion.resolve.resolver.FuzzyMatch.compare` \{#agrag-ingestion-resolve-resolver-FuzzyMatch-compare}

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Return a verdict from token-sort-ratio similarity.

###### `agrag.ingestion.resolve.resolver.FuzzyMatch.compare_with_evidence` \{#agrag-ingestion-resolve-resolver-FuzzyMatch-compare_with_evidence}

```python
compare_with_evidence(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonResult
```

Compare two entities and include their token-sort similarity.

###### `agrag.ingestion.resolve.resolver.FuzzyMatch.match_above` \{#agrag-ingestion-resolve-resolver-FuzzyMatch-match_above}

```python
match_above = match_above
```

##### `agrag.ingestion.resolve.resolver.LLMVerify` \{#agrag-ingestion-resolve-resolver-LLMVerify}

```python
LLMVerify(*, chunks_by_id:dict[UUID, Chunk], settings:ExtractionLLMSettings | None = None, client:object | None = None, max_pairs_per_batch:int = 50, tracer:Tracer | None = None) -> None
```

Bases: <code>[Comparator](#agrag-ingestion-resolve-resolver-Comparator)</code>

Asks an LLM to verify an ambiguous pair. Last resort; never UNCERTAIN.

Never raises from an LLM-call failure: it resolves to NO_MATCH instead, by
the same fail-safe design as every comparator a Resolver runs — an
ambiguous or failed comparison never merges two entities. A missing package
extra is a configuration error, not an ambiguous judgment call, and is
raised outright instead (see compare's Raises section).

**Functions:**

- [**compare**](#agrag-ingestion-resolve-resolver-LLMVerify-compare) – Return the LLM's verdict for one pair, or NO_MATCH on failure.
- [**compare_batch**](#agrag-ingestion-resolve-resolver-LLMVerify-compare_batch) – Verify ambiguous candidate pairs across bounded LLM requests.
- [**compare_batch_detailed**](#agrag-ingestion-resolve-resolver-LLMVerify-compare_batch_detailed) – Verify pairs and count how many verdicts came back uncertain.
- [**compare_with_evidence**](#agrag-ingestion-resolve-resolver-LLMVerify-compare_with_evidence) – Compare two entities and retain any available decision evidence.

**Attributes:**

- [**chunks_by_id**](#agrag-ingestion-resolve-resolver-LLMVerify-chunks_by_id) –
- [**failed_requests**](#agrag-ingestion-resolve-resolver-LLMVerify-failed_requests) (<code>int</code>) –
- [**max_pairs_per_batch**](#agrag-ingestion-resolve-resolver-LLMVerify-max_pairs_per_batch) –
- [**settings**](#agrag-ingestion-resolve-resolver-LLMVerify-settings) –

**Parameters:**

- **chunks_by_id** (<code>dict\[UUID, [Chunk](common.md#agrag-common-data_models-chunk-Chunk)\]</code>) – Maps a Chunk id to the Chunk, for prompt context.
- **settings** (<code>[ExtractionLLMSettings](#agrag-ingestion-extract-ExtractionLLMSettings) | None</code>) – LLM client config. Defaults to `ExtractionLLMSettings()`.
  Ignored when `client` is given: an injected client also
  disables `settings.retry`, since a caller building its own
  client is assumed to own its own retry behavior too.
- **client** (<code>object | None</code>) – An already-built BAML client. Tests inject a fake here.
- **max_pairs_per_batch** (<code>int</code>) – Maximum pairs sent to the LLM in one request.
  A large ambiguous population is split into requests of at most
  this size so one oversized request cannot exceed the model's
  context limit and silently fail every pair in the batch.
- **tracer** (<code>Tracer | None</code>) – Opens the `agrag.resolution.llm_verify` span and the
  LLM call spans below it.

###### `agrag.ingestion.resolve.resolver.LLMVerify.chunks_by_id` \{#agrag-ingestion-resolve-resolver-LLMVerify-chunks_by_id}

```python
chunks_by_id = chunks_by_id
```

###### `agrag.ingestion.resolve.resolver.LLMVerify.compare` \{#agrag-ingestion-resolve-resolver-LLMVerify-compare}

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Return the LLM's verdict for one pair, or NO_MATCH on failure.

Runs through compare_batch so the single-pair path shares the
batch validation and fail-safe behavior.

**Raises:**

- <code>[ExtractorMissingExtraError](#agrag-ingestion-extract-ExtractorMissingExtraError)</code> – The `llm` package extra is not
  installed.

###### `agrag.ingestion.resolve.resolver.LLMVerify.compare_batch` \{#agrag-ingestion-resolve-resolver-LLMVerify-compare_batch}

```python
compare_batch(pairs:list[tuple[int, int, ExtractedEntity, ExtractedEntity]], *, similarities:dict[tuple[int, int], float] | None = None, neighbors_by_index:dict[int, list[str]] | None = None) -> dict[tuple[int, int], ComparisonResult]
```

Verify ambiguous candidate pairs across bounded LLM requests.

Splits into requests of at most `max_pairs_per_batch` pairs so one
oversized population cannot exceed the model's context limit.
Invalid, missing, and uncertain model responses do not merge entities.

**Parameters:**

- **pairs** (<code>list\[tuple\[int, int, [ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity), [ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity)\]\]</code>) – `(left_index, right_index, left, right)` tuples to verify.
- **similarities** (<code>dict\[tuple\[int, int\], float\] | None</code>) – Embedding similarity per pair, sent to the model
  as decision context. Defaults to 0.0 when unknown.
- **neighbors_by_index** (<code>dict\[int, list\[str\]\] | None</code>) – Entity index to its neighboring-relationship
  context strings. Looked up globally, so every chunk sees the
  same map.

###### `agrag.ingestion.resolve.resolver.LLMVerify.compare_batch_detailed` \{#agrag-ingestion-resolve-resolver-LLMVerify-compare_batch_detailed}

```python
compare_batch_detailed(pairs:list[tuple[int, int, ExtractedEntity, ExtractedEntity]], *, similarities:dict[tuple[int, int], float] | None = None, neighbors_by_index:dict[int, list[str]] | None = None) -> tuple[dict[tuple[int, int], ComparisonResult], int]
```

Verify pairs and count how many verdicts came back uncertain.

**Parameters:**

- **pairs** (<code>list\[tuple\[int, int, [ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity), [ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity)\]\]</code>) – The candidate pairs to verify.
- **similarities** (<code>dict\[tuple\[int, int\], float\] | None</code>) – Embedding similarity per pair, sent to the model
  as decision context. Defaults to 0.0 when unknown.
- **neighbors_by_index** (<code>dict\[int, list\[str\]\] | None</code>) – Entity index to its neighboring-relationship
  context strings. Looked up globally, so every chunk sees the
  same map.

**Returns:**

- <code>dict\[tuple\[int, int\], [ComparisonResult](#agrag-ingestion-resolve-resolver-ComparisonResult)\]</code> – The per-pair results and the count of raw uncertain verdicts,
- <code>int</code> – before the fail-safe maps them to NO_MATCH. A request that
- <code>tuple\[dict\[tuple\[int, int\], [ComparisonResult](#agrag-ingestion-resolve-resolver-ComparisonResult)\], int\]</code> – errors maps its pairs to NO_MATCH and increments
- <code>tuple\[dict\[tuple\[int, int\], [ComparisonResult](#agrag-ingestion-resolve-resolver-ComparisonResult)\], int\]</code> – failed_requests.

###### `agrag.ingestion.resolve.resolver.LLMVerify.compare_with_evidence` \{#agrag-ingestion-resolve-resolver-LLMVerify-compare_with_evidence}

```python
compare_with_evidence(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonResult
```

Compare two entities and retain any available decision evidence.

###### `agrag.ingestion.resolve.resolver.LLMVerify.failed_requests` \{#agrag-ingestion-resolve-resolver-LLMVerify-failed_requests}

```python
failed_requests: int = 0
```

###### `agrag.ingestion.resolve.resolver.LLMVerify.max_pairs_per_batch` \{#agrag-ingestion-resolve-resolver-LLMVerify-max_pairs_per_batch}

```python
max_pairs_per_batch = max_pairs_per_batch
```

###### `agrag.ingestion.resolve.resolver.LLMVerify.settings` \{#agrag-ingestion-resolve-resolver-LLMVerify-settings}

```python
settings = settings
```

##### `agrag.ingestion.resolve.resolver.ResolutionGroup` \{#agrag-ingestion-resolve-resolver-ResolutionGroup}

Bases: <code>BaseModel</code>

One set of ExtractedEntity indices resolution decided are the same entity.

**Attributes:**

- [**entity_indices**](#agrag-ingestion-resolve-resolver-ResolutionGroup-entity_indices) (<code>list\[int\]</code>) – Indices into the entity list passed to Resolver.resolve.
  A group of one means resolution found no match for that entity.

###### `agrag.ingestion.resolve.resolver.ResolutionGroup.entity_indices` \{#agrag-ingestion-resolve-resolver-ResolutionGroup-entity_indices}

```python
entity_indices: list[int]
```

##### `agrag.ingestion.resolve.resolver.ResolutionResult` \{#agrag-ingestion-resolve-resolver-ResolutionResult}

Bases: <code>BaseModel</code>

The groups, non-exact evidence, and ambiguity count of one pass.

**Attributes:**

- [**groups**](#agrag-ingestion-resolve-resolver-ResolutionResult-groups) (<code>list\[[ResolutionGroup](#agrag-ingestion-resolve-resolver-ResolutionGroup)\]</code>) – One group per transitively connected mention set.
- [**matches**](#agrag-ingestion-resolve-resolver-ResolutionResult-matches) (<code>list\[[ResolvedMatch](#agrag-ingestion-resolve-resolver-ResolvedMatch)\]</code>) – Evidence for every confirmed non-exact pair.
- [**ambiguous_count**](#agrag-ingestion-resolve-resolver-ResolutionResult-ambiguous_count) (<code>int</code>) – LLM verdicts that came back uncertain. These
  pairs never merge.
- [**failed_llm_requests**](#agrag-ingestion-resolve-resolver-ResolutionResult-failed_llm_requests) (<code>int</code>) – LLM verification requests that errored
  and were mapped to "no match".
- [**cap_truncated_pairs**](#agrag-ingestion-resolve-resolver-ResolutionResult-cap_truncated_pairs) (<code>int</code>) – Boundary pairs that never reached the LLM
  because of the per-label pair cap.

###### `agrag.ingestion.resolve.resolver.ResolutionResult.ambiguous_count` \{#agrag-ingestion-resolve-resolver-ResolutionResult-ambiguous_count}

```python
ambiguous_count: int = 0
```

###### `agrag.ingestion.resolve.resolver.ResolutionResult.cap_truncated_pairs` \{#agrag-ingestion-resolve-resolver-ResolutionResult-cap_truncated_pairs}

```python
cap_truncated_pairs: int = 0
```

###### `agrag.ingestion.resolve.resolver.ResolutionResult.failed_llm_requests` \{#agrag-ingestion-resolve-resolver-ResolutionResult-failed_llm_requests}

```python
failed_llm_requests: int = 0
```

###### `agrag.ingestion.resolve.resolver.ResolutionResult.groups` \{#agrag-ingestion-resolve-resolver-ResolutionResult-groups}

```python
groups: list[ResolutionGroup]
```

###### `agrag.ingestion.resolve.resolver.ResolutionResult.matches` \{#agrag-ingestion-resolve-resolver-ResolutionResult-matches}

```python
matches: list[ResolvedMatch]
```

##### `agrag.ingestion.resolve.resolver.ResolvedMatch` \{#agrag-ingestion-resolve-resolver-ResolvedMatch}

Bases: <code>BaseModel</code>

One confirmed non-exact match between two input entity indices.

Exact-name identity matches group mentions but do not create a match-graph
edge. Every other confirmed comparator decision creates one record.

**Attributes:**

- [**comparator**](#agrag-ingestion-resolve-resolver-ResolvedMatch-comparator) (<code>str</code>) –
- [**decided_at**](#agrag-ingestion-resolve-resolver-ResolvedMatch-decided_at) (<code>datetime</code>) –
- [**left_index**](#agrag-ingestion-resolve-resolver-ResolvedMatch-left_index) (<code>int</code>) –
- [**reasoning**](#agrag-ingestion-resolve-resolver-ResolvedMatch-reasoning) (<code>str | None</code>) –
- [**right_index**](#agrag-ingestion-resolve-resolver-ResolvedMatch-right_index) (<code>int</code>) –
- [**score**](#agrag-ingestion-resolve-resolver-ResolvedMatch-score) (<code>float | None</code>) –

###### `agrag.ingestion.resolve.resolver.ResolvedMatch.comparator` \{#agrag-ingestion-resolve-resolver-ResolvedMatch-comparator}

```python
comparator: str
```

###### `agrag.ingestion.resolve.resolver.ResolvedMatch.decided_at` \{#agrag-ingestion-resolve-resolver-ResolvedMatch-decided_at}

```python
decided_at: datetime
```

###### `agrag.ingestion.resolve.resolver.ResolvedMatch.left_index` \{#agrag-ingestion-resolve-resolver-ResolvedMatch-left_index}

```python
left_index: int
```

###### `agrag.ingestion.resolve.resolver.ResolvedMatch.reasoning` \{#agrag-ingestion-resolve-resolver-ResolvedMatch-reasoning}

```python
reasoning: str | None = None
```

###### `agrag.ingestion.resolve.resolver.ResolvedMatch.right_index` \{#agrag-ingestion-resolve-resolver-ResolvedMatch-right_index}

```python
right_index: int
```

###### `agrag.ingestion.resolve.resolver.ResolvedMatch.score` \{#agrag-ingestion-resolve-resolver-ResolvedMatch-score}

```python
score: float | None = None
```

##### `agrag.ingestion.resolve.resolver.Resolver` \{#agrag-ingestion-resolve-resolver-Resolver}

```python
Resolver(*, comparators:list[Comparator], candidate_source:CandidateSource, embedder:Embedder | None = None, hard_merge_threshold:float = HARD_MERGE_THRESHOLD, discard_threshold:float = DISCARD_THRESHOLD, max_llm_pairs:int = MAX_LLM_PAIRS, llm_batch_size:int = 10, tracer:Tracer | None = None) -> None
```

Routes blocked candidate pairs through exact, fuzzy, embedding, and LLM zones.

Exact identity groups mentions without evidence. A near-identical
fuzzy score merges on the fast path. Every other pair consults its
embedding cosine similarity: at or above the hard-merge threshold it
merges, below the discard threshold it drops, and inside the band it
needs LLM review, capped per label. Tight ambiguous sub-clusters
merge without spending LLM calls.

**Functions:**

- [**resolve**](#agrag-ingestion-resolve-resolver-Resolver-resolve) – Resolve entity groups and retain each confirmed non-exact match.

**Attributes:**

- [**candidate_source**](#agrag-ingestion-resolve-resolver-Resolver-candidate_source) –
- [**comparators**](#agrag-ingestion-resolve-resolver-Resolver-comparators) –
- [**discard_threshold**](#agrag-ingestion-resolve-resolver-Resolver-discard_threshold) –
- [**embedder**](#agrag-ingestion-resolve-resolver-Resolver-embedder) –
- [**hard_merge_threshold**](#agrag-ingestion-resolve-resolver-Resolver-hard_merge_threshold) –
- [**llm_batch_size**](#agrag-ingestion-resolve-resolver-Resolver-llm_batch_size) –
- [**max_llm_pairs**](#agrag-ingestion-resolve-resolver-Resolver-max_llm_pairs) –

**Parameters:**

- **comparators** (<code>list\[[Comparator](#agrag-ingestion-resolve-resolver-Comparator)\]</code>) – The ExactMatch, FuzzyMatch, and LLMVerify tiers,
  each picked out by type. A missing ExactMatch or FuzzyMatch
  falls back to its defaults; without an LLMVerify the LLM
  tier is skipped and boundary pairs never merge.
- **candidate_source** (<code>[CandidateSource](#agrag-ingestion-resolve-candidate_source-CandidateSource)</code>) – Narrows which pairs get compared at all.
- **embedder** (<code>[Embedder](embedding.md#agrag-embedding-base-Embedder) | None</code>) – Embeds mention texts for the similarity tier. None
  skips that tier: every fuzzy-uncertain pair counts as
  ambiguous, ranked by its fuzzy score.
- **hard_merge_threshold** (<code>float</code>) – Embedding similarity at or above which
  a pair merges without LLM review.
- **discard_threshold** (<code>float</code>) – Embedding similarity below which a pair
  drops without LLM review.
- **max_llm_pairs** (<code>int</code>) – Maximum ambiguous pairs sent to the LLM per
  label.
- **llm_batch_size** (<code>int</code>) – Pairs per LLM request. Must fit the
  LLMVerify comparator's max_pairs_per_batch.
- **tracer** (<code>Tracer | None</code>) – Opens this resolver's spans.

**Raises:**

- <code>ValueError</code> – llm_batch_size is not positive, or exceeds the
  LLMVerify comparator's max_pairs_per_batch.

###### `agrag.ingestion.resolve.resolver.Resolver.candidate_source` \{#agrag-ingestion-resolve-resolver-Resolver-candidate_source}

```python
candidate_source = candidate_source
```

###### `agrag.ingestion.resolve.resolver.Resolver.comparators` \{#agrag-ingestion-resolve-resolver-Resolver-comparators}

```python
comparators = comparators
```

###### `agrag.ingestion.resolve.resolver.Resolver.discard_threshold` \{#agrag-ingestion-resolve-resolver-Resolver-discard_threshold}

```python
discard_threshold = discard_threshold
```

###### `agrag.ingestion.resolve.resolver.Resolver.embedder` \{#agrag-ingestion-resolve-resolver-Resolver-embedder}

```python
embedder = embedder
```

###### `agrag.ingestion.resolve.resolver.Resolver.hard_merge_threshold` \{#agrag-ingestion-resolve-resolver-Resolver-hard_merge_threshold}

```python
hard_merge_threshold = hard_merge_threshold
```

###### `agrag.ingestion.resolve.resolver.Resolver.llm_batch_size` \{#agrag-ingestion-resolve-resolver-Resolver-llm_batch_size}

```python
llm_batch_size = llm_batch_size
```

###### `agrag.ingestion.resolve.resolver.Resolver.max_llm_pairs` \{#agrag-ingestion-resolve-resolver-Resolver-max_llm_pairs}

```python
max_llm_pairs = max_llm_pairs
```

###### `agrag.ingestion.resolve.resolver.Resolver.resolve` \{#agrag-ingestion-resolve-resolver-Resolver-resolve}

```python
resolve(entities:list[ExtractedEntity], *, neighbors_by_index:dict[int, list[str]] | None = None, similarity_by_pair:dict[tuple[int, int], float] | None = None) -> ResolutionResult
```

Resolve entity groups and retain each confirmed non-exact match.

**Parameters:**

- **entities** (<code>list\[[ExtractedEntity](common.md#agrag-common-data_models-extraction-ExtractedEntity)\]</code>) – The entities to resolve. Only entities passed in the
  same call are ever compared against each other — resolving
  against previously-resolved entities from an earlier call is
  not supported by this Resolver.
- **neighbors_by_index** (<code>dict\[int, list\[str\]\] | None</code>) – Entity index to that entity's neighboring-
  relationship context for LLM verification, when the caller has
  such a source. Omitted by callers that do not.
- **similarity_by_pair** (<code>dict\[tuple\[int, int\], float\] | None</code>) – Already-known real similarity scores keyed by
  `(min(left, right), max(left, right))`, such as an ANN
  backend's hit score. Never drives zone routing -- that scale
  is not comparable to this Resolver's own cosine similarity --
  but reaches the LLM as decision context, preferred over a
  freshly embedded score, for a pair that lands on the boundary
  anyway. Not mutated.

**Returns:**

- <code>[ResolutionResult](#agrag-ingestion-resolve-resolver-ResolutionResult)</code> – Groups for every input index, evidence for every confirmed
- <code>[ResolutionResult](#agrag-ingestion-resolve-resolver-ResolutionResult)</code> – non-exact pair, the count of uncertain LLM verdicts, and the
- <code>[ResolutionResult](#agrag-ingestion-resolve-resolver-ResolutionResult)</code> – counts of failed LLM requests and cap-truncated pairs.

##### `agrag.ingestion.resolve.resolver.logger` \{#agrag-ingestion-resolve-resolver-logger}

```python
logger = logging.getLogger(__name__)
```

#### `agrag.ingestion.resolve.zone_classifier` \{#agrag-ingestion-resolve-zone_classifier}

Zone classification for entity-resolution candidate pairs.

**Functions:**

- [**classify_zone**](#agrag-ingestion-resolve-zone_classifier-classify_zone) – Assign a candidate pair to a resolution zone.
- [**precluster_ambiguous**](#agrag-ingestion-resolve-zone_classifier-precluster_ambiguous) – Find tight ambiguous sub-clusters that can merge without LLM review.
- [**select_llm_pairs**](#agrag-ingestion-resolve-zone_classifier-select_llm_pairs) – Rank ambiguous candidates for LLM review, most similar first.

**Attributes:**

- [**DISCARD_THRESHOLD**](#agrag-ingestion-resolve-zone_classifier-DISCARD_THRESHOLD) –
- [**FUZZY_FAST_PATH_THRESHOLD**](#agrag-ingestion-resolve-zone_classifier-FUZZY_FAST_PATH_THRESHOLD) –
- [**HARD_MERGE_THRESHOLD**](#agrag-ingestion-resolve-zone_classifier-HARD_MERGE_THRESHOLD) –
- [**MAX_LLM_PAIRS**](#agrag-ingestion-resolve-zone_classifier-MAX_LLM_PAIRS) –

##### `agrag.ingestion.resolve.zone_classifier.DISCARD_THRESHOLD` \{#agrag-ingestion-resolve-zone_classifier-DISCARD_THRESHOLD}

```python
DISCARD_THRESHOLD = 0.8
```

##### `agrag.ingestion.resolve.zone_classifier.FUZZY_FAST_PATH_THRESHOLD` \{#agrag-ingestion-resolve-zone_classifier-FUZZY_FAST_PATH_THRESHOLD}

```python
FUZZY_FAST_PATH_THRESHOLD = 0.97
```

##### `agrag.ingestion.resolve.zone_classifier.HARD_MERGE_THRESHOLD` \{#agrag-ingestion-resolve-zone_classifier-HARD_MERGE_THRESHOLD}

```python
HARD_MERGE_THRESHOLD = 0.95
```

##### `agrag.ingestion.resolve.zone_classifier.MAX_LLM_PAIRS` \{#agrag-ingestion-resolve-zone_classifier-MAX_LLM_PAIRS}

```python
MAX_LLM_PAIRS = 500
```

##### `agrag.ingestion.resolve.zone_classifier.classify_zone` \{#agrag-ingestion-resolve-zone_classifier-classify_zone}

```python
classify_zone(fuzzy_score:float, embedding_similarity:float | None) -> str
```

Assign a candidate pair to a resolution zone.

A near-identical fuzzy score merges without consulting the embedding.
Otherwise the embedding similarity decides: at or above the hard-merge
threshold the pair merges, inside the discard-to-hard-merge band it
needs LLM review, and below the discard threshold it is dropped. A
missing embedding with a below-fast-path fuzzy score also discards,
since no signal supports a merge.

**Parameters:**

- **fuzzy_score** (<code>float</code>) – Token-sort-ratio similarity in `[0, 1]`.
- **embedding_similarity** (<code>float | None</code>) – Cosine similarity in `[-1, 1]`, or `None`
  when no embedding is available.

**Returns:**

- <code>str</code> – `"hard_merge"`, `"ambiguous"`, or `"discard"`.

##### `agrag.ingestion.resolve.zone_classifier.precluster_ambiguous` \{#agrag-ingestion-resolve-zone_classifier-precluster_ambiguous}

```python
precluster_ambiguous(ids:list[UUID], similarities:Mapping[tuple[int, int], float], *, hard_merge_threshold:float = HARD_MERGE_THRESHOLD) -> list[list[UUID]]
```

Find tight ambiguous sub-clusters that can merge without LLM review.

Runs average-linkage clustering cut at `1 - HARD_MERGE_THRESHOLD` so
only groups whose mean pairwise distance sits inside the hard-merge
zone come back. Pairs absent from `similarities` count as maximally
distant and never join a group.

**Parameters:**

- **ids** (<code>list\[UUID\]</code>) – Candidate entity identifiers.
- **similarities** (<code>Mapping\[tuple\[int, int\], float\]</code>) – Cosine similarity keyed by `(left, right)` index
  into `ids`, symmetric entries optional.
- **hard_merge_threshold** (<code>float</code>) – Similarity required for an automatic merge.

**Returns:**

- <code>list\[list\[UUID\]\]</code> – Only multi-member groups; singletons need LLM review or discard.

##### `agrag.ingestion.resolve.zone_classifier.select_llm_pairs` \{#agrag-ingestion-resolve-zone_classifier-select_llm_pairs}

```python
select_llm_pairs(candidates:list[tuple[int, int, float]], *, max_pairs:int = MAX_LLM_PAIRS) -> list[tuple[int, int]]
```

Rank ambiguous candidates for LLM review, most similar first.

**Parameters:**

- **candidates** (<code>list\[tuple\[int, int, float\]\]</code>) – `(left_index, right_index, similarity)` triples.
- **max_pairs** (<code>int</code>) – Maximum pairs to return.

**Returns:**

- <code>list\[tuple\[int, int\]\]</code> – Index pairs ordered by similarity descending, capped at
- <code>list\[tuple\[int, int\]\]</code> – `max_pairs`.

### `agrag.ingestion.resolved_embeddings` \{#agrag-ingestion-resolved_embeddings}

Embedding and vector synchronization for resolved-entities.

**Functions:**

- [**embed_resolved_entities**](#agrag-ingestion-resolved_embeddings-embed_resolved_entities) – Write resolved-entity embeddings to the graph and optional vector store.

#### `agrag.ingestion.resolved_embeddings.embed_resolved_entities` \{#agrag-ingestion-resolved_embeddings-embed_resolved_entities}

```python
embed_resolved_entities(entities:list[ResolvedEntity], *, embedder:Embedder, graph_store:GraphStore, vector_store:VectorStore | None, vector_collection:str, error_policy:ErrorPolicy, pending_job_id:UUID | str | None = None) -> list[StageFailure]
```

Write resolved-entity embeddings to the graph and optional vector store.

Graph writes finish before vector-store synchronization because the two
stores cannot share a transaction. A failed sync clears the graph vector,
removes any old mirrored vector, and records `failed` for a later
rebuild pass to retry.

Only entities whose guarded graph write actually matched a live node are
mirrored to the vector store or have their sync status updated. A
concurrent rebuild can replace or delete a ResolvedEntity between
this call reading it and writing its embedding; skipping the unmatched
ones keeps this call from resurrecting a vector, or overwriting a status,
that the concurrent call already owns.

### `agrag.ingestion.resolved_entities` \{#agrag-ingestion-resolved_entities}

Non-destructive match persistence and resolved-entity computation.

**Classes:**

- [**DeactivationResult**](#agrag-ingestion-resolved_entities-DeactivationResult) – Resolved entities created after a match correction and stale ids removed.
- [**MatchDecision**](#agrag-ingestion-resolved_entities-MatchDecision) – A confirmed non-exact entity match ready to persist.
- [**PruningResult**](#agrag-ingestion-resolved_entities-PruningResult) – Ids removed and clusters rebuilt by deletion-triggered pruning.
- [**RebuildResult**](#agrag-ingestion-resolved_entities-RebuildResult) – The derived entity created and prior derived ids it replaced.

**Functions:**

- [**compute_resolved_entity**](#agrag-ingestion-resolved_entities-compute_resolved_entity) – Compute a resolved entity from its current member data only.
- [**deactivate_match_and_rebuild**](#agrag-ingestion-resolved_entities-deactivate_match_and_rebuild) – Deactivate a match and return its replacements and deleted derived IDs.
- [**decisions_by_component**](#agrag-ingestion-resolved_entities-decisions_by_component) – Map resolution evidence to raw ids and group it by connected component.
- [**match_decision_components**](#agrag-ingestion-resolved_entities-match_decision_components) – Group persisted match decisions by their connected raw component.
- [**matches_id**](#agrag-ingestion-resolved_entities-matches_id) – Return the order-independent deterministic id for an entity match.
- [**prune_orphaned_entities**](#agrag-ingestion-resolved_entities-prune_orphaned_entities) – Delete candidates with no open-chunk evidence and rebuild clusters.
- [**rebuild_resolved_entities**](#agrag-ingestion-resolved_entities-rebuild_resolved_entities) – Rebuild the resolved entity of each committed component from its seeds.
- [**write_matches_and_rebuild**](#agrag-ingestion-resolved_entities-write_matches_and_rebuild) – Persist matches and rebuild their supplied connected component.

**Attributes:**

- [**MatchComponent**](#agrag-ingestion-resolved_entities-MatchComponent) – One connected component: its match decisions and its raw member entities.

#### `agrag.ingestion.resolved_entities.DeactivationResult` \{#agrag-ingestion-resolved_entities-DeactivationResult}

Bases: <code>BaseModel</code>

Resolved entities created after a match correction and stale ids removed.

**Attributes:**

- [**removed_entity_ids**](#agrag-ingestion-resolved_entities-DeactivationResult-removed_entity_ids) (<code>list\[UUID\]</code>) –
- [**resolved_entities**](#agrag-ingestion-resolved_entities-DeactivationResult-resolved_entities) (<code>list\[[ResolvedEntity](common.md#agrag-common-data_models-resolved_entity-ResolvedEntity)\]</code>) –

##### `agrag.ingestion.resolved_entities.DeactivationResult.removed_entity_ids` \{#agrag-ingestion-resolved_entities-DeactivationResult-removed_entity_ids}

```python
removed_entity_ids: list[UUID]
```

##### `agrag.ingestion.resolved_entities.DeactivationResult.resolved_entities` \{#agrag-ingestion-resolved_entities-DeactivationResult-resolved_entities}

```python
resolved_entities: list[ResolvedEntity]
```

#### `agrag.ingestion.resolved_entities.MatchComponent` \{#agrag-ingestion-resolved_entities-MatchComponent}

```python
MatchComponent = tuple[list[MatchDecision], list[Entity]]
```

One connected component: its match decisions and its raw member entities.

#### `agrag.ingestion.resolved_entities.MatchDecision` \{#agrag-ingestion-resolved_entities-MatchDecision}

Bases: <code>BaseModel</code>

A confirmed non-exact entity match ready to persist.

**Attributes:**

- [**comparator**](#agrag-ingestion-resolved_entities-MatchDecision-comparator) (<code>str</code>) –
- [**decided_at**](#agrag-ingestion-resolved_entities-MatchDecision-decided_at) (<code>datetime</code>) –
- [**entity_a_id**](#agrag-ingestion-resolved_entities-MatchDecision-entity_a_id) (<code>UUID</code>) –
- [**entity_b_id**](#agrag-ingestion-resolved_entities-MatchDecision-entity_b_id) (<code>UUID</code>) –
- [**reasoning**](#agrag-ingestion-resolved_entities-MatchDecision-reasoning) (<code>str | None</code>) –
- [**score**](#agrag-ingestion-resolved_entities-MatchDecision-score) (<code>float | None</code>) –

##### `agrag.ingestion.resolved_entities.MatchDecision.comparator` \{#agrag-ingestion-resolved_entities-MatchDecision-comparator}

```python
comparator: str
```

##### `agrag.ingestion.resolved_entities.MatchDecision.decided_at` \{#agrag-ingestion-resolved_entities-MatchDecision-decided_at}

```python
decided_at: datetime
```

##### `agrag.ingestion.resolved_entities.MatchDecision.entity_a_id` \{#agrag-ingestion-resolved_entities-MatchDecision-entity_a_id}

```python
entity_a_id: UUID
```

##### `agrag.ingestion.resolved_entities.MatchDecision.entity_b_id` \{#agrag-ingestion-resolved_entities-MatchDecision-entity_b_id}

```python
entity_b_id: UUID
```

##### `agrag.ingestion.resolved_entities.MatchDecision.reasoning` \{#agrag-ingestion-resolved_entities-MatchDecision-reasoning}

```python
reasoning: str | None = None
```

##### `agrag.ingestion.resolved_entities.MatchDecision.score` \{#agrag-ingestion-resolved_entities-MatchDecision-score}

```python
score: float | None = None
```

#### `agrag.ingestion.resolved_entities.PruningResult` \{#agrag-ingestion-resolved_entities-PruningResult}

Bases: <code>BaseModel</code>

Ids removed and clusters rebuilt by deletion-triggered pruning.

**Attributes:**

- [**rebuilt_entities**](#agrag-ingestion-resolved_entities-PruningResult-rebuilt_entities) (<code>list\[[ResolvedEntity](common.md#agrag-common-data_models-resolved_entity-ResolvedEntity)\]</code>) –
- [**removed_entity_ids**](#agrag-ingestion-resolved_entities-PruningResult-removed_entity_ids) (<code>list\[UUID\]</code>) –
- [**removed_resolved_entity_ids**](#agrag-ingestion-resolved_entities-PruningResult-removed_resolved_entity_ids) (<code>list\[UUID\]</code>) –

##### `agrag.ingestion.resolved_entities.PruningResult.rebuilt_entities` \{#agrag-ingestion-resolved_entities-PruningResult-rebuilt_entities}

```python
rebuilt_entities: list[ResolvedEntity]
```

##### `agrag.ingestion.resolved_entities.PruningResult.removed_entity_ids` \{#agrag-ingestion-resolved_entities-PruningResult-removed_entity_ids}

```python
removed_entity_ids: list[UUID]
```

##### `agrag.ingestion.resolved_entities.PruningResult.removed_resolved_entity_ids` \{#agrag-ingestion-resolved_entities-PruningResult-removed_resolved_entity_ids}

```python
removed_resolved_entity_ids: list[UUID]
```

#### `agrag.ingestion.resolved_entities.RebuildResult` \{#agrag-ingestion-resolved_entities-RebuildResult}

Bases: <code>BaseModel</code>

The derived entity created and prior derived ids it replaced.

**Attributes:**

- [**removed_entity_ids**](#agrag-ingestion-resolved_entities-RebuildResult-removed_entity_ids) (<code>list\[UUID\]</code>) –
- [**resolved_entity**](#agrag-ingestion-resolved_entities-RebuildResult-resolved_entity) (<code>[ResolvedEntity](common.md#agrag-common-data_models-resolved_entity-ResolvedEntity)</code>) –

##### `agrag.ingestion.resolved_entities.RebuildResult.removed_entity_ids` \{#agrag-ingestion-resolved_entities-RebuildResult-removed_entity_ids}

```python
removed_entity_ids: list[UUID]
```

##### `agrag.ingestion.resolved_entities.RebuildResult.resolved_entity` \{#agrag-ingestion-resolved_entities-RebuildResult-resolved_entity}

```python
resolved_entity: ResolvedEntity
```

#### `agrag.ingestion.resolved_entities.compute_resolved_entity` \{#agrag-ingestion-resolved_entities-compute_resolved_entity}

```python
compute_resolved_entity(members:list[Entity], schema:GraphSchema, *, tracer:Tracer | None = None) -> ResolvedEntity
```

Compute a resolved entity from its current member data only.

#### `agrag.ingestion.resolved_entities.deactivate_match_and_rebuild` \{#agrag-ingestion-resolved_entities-deactivate_match_and_rebuild}

```python
deactivate_match_and_rebuild(match_id:UUID, *, graph_store:GraphStore, schema:GraphSchema, tracer:Tracer | None = None) -> DeactivationResult
```

Deactivate a match and return its replacements and deleted derived IDs.

#### `agrag.ingestion.resolved_entities.decisions_by_component` \{#agrag-ingestion-resolved_entities-decisions_by_component}

```python
decisions_by_component(matches:list[ResolvedMatch], mention_to_entity:dict[int, UUID]) -> list[list[MatchDecision]]
```

Map resolution evidence to raw ids and group it by connected component.

#### `agrag.ingestion.resolved_entities.match_decision_components` \{#agrag-ingestion-resolved_entities-match_decision_components}

```python
match_decision_components(decisions:list[MatchDecision]) -> list[list[MatchDecision]]
```

Group persisted match decisions by their connected raw component.

#### `agrag.ingestion.resolved_entities.matches_id` \{#agrag-ingestion-resolved_entities-matches_id}

```python
matches_id(entity_a_id:UUID, entity_b_id:UUID) -> UUID
```

Return the order-independent deterministic id for an entity match.

#### `agrag.ingestion.resolved_entities.prune_orphaned_entities` \{#agrag-ingestion-resolved_entities-prune_orphaned_entities}

```python
prune_orphaned_entities(candidate_entity_ids:list[UUID], *, graph_store:GraphStore, schema:GraphSchema, tracer:Tracer | None = None) -> PruningResult
```

Delete candidates with no open-chunk evidence and rebuild clusters.

A candidate mentioned by any chunk with an open PART_OF edge keeps its
node. Any other candidate loses its node with its incident MENTIONED_IN
and RESOLVED_AS edges; each affected cluster is then recomputed over
its remaining members, or deleted when fewer than two remain and the
survivor returns to plain status. Merge aliases owned by removed
entities are deleted too, so re-ingesting a pruned name starts clean
instead of colliding with an alias pointing at a missing node.

Only the supplied candidates are ever deleted. Evidence is checked per
candidate id, never with a graph-wide scan.

#### `agrag.ingestion.resolved_entities.rebuild_resolved_entities` \{#agrag-ingestion-resolved_entities-rebuild_resolved_entities}

```python
rebuild_resolved_entities(seed_ids:list[UUID], *, graph_store:GraphStore, schema:GraphSchema, tracer:Tracer | None = None) -> list[RebuildResult]
```

Rebuild the resolved entity of each committed component from its seeds.

The matches already exist, so no match decision is written or changed.
The resolved nodes and their `RESOLVED_AS` memberships are rebuilt,
each membership carrying the newest committed match time when one
exists. Each component is read as it stands now, replacing whatever
resolved entities its members belonged to. A seed whose entity is
gone, or whose component has fewer than two members, is skipped:
nothing is left to rebuild for it. Safe to run again on the same
seeds.

**Parameters:**

- **seed_ids** (<code>list\[UUID\]</code>) – One member id per component to rebuild. Seeds that share a
  component rebuild it once.
- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Where the components are read and rewritten.
- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The schema the members belong to.
- **tracer** (<code>Tracer | None</code>) – Passed to description summarization.

**Returns:**

- <code>list\[[RebuildResult](#agrag-ingestion-resolved_entities-RebuildResult)\]</code> – One result per rebuilt component, in seed order.

#### `agrag.ingestion.resolved_entities.write_matches_and_rebuild` \{#agrag-ingestion-resolved_entities-write_matches_and_rebuild}

```python
write_matches_and_rebuild(decisions:list[MatchDecision], *, graph_store:GraphStore, schema:GraphSchema, members:list[Entity], pending_job_id:str | None = None, tracer:Tracer | None = None) -> RebuildResult
```

Persist matches and rebuild their supplied connected component.

Callers fetch the bounded affected component before invoking this function.
The resolved node is always recomputed from that current membership.

**Parameters:**

- **decisions** (<code>list\[[MatchDecision](#agrag-ingestion-resolved_entities-MatchDecision)\]</code>) – The confirmed matches to persist.
- **graph_store** (<code>[GraphStore](graphdb.md#agrag-graphdb-base-GraphStore)</code>) – Where matches and resolved entities are written.
- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The schema the members belong to.
- **members** (<code>list\[[Entity](common.md#agrag-common-data_models-entity-Entity)\]</code>) – The component members the resolved node is computed from.
- **pending_job_id** (<code>str | None</code>) – The in-flight Cutover Job's id, tagging the match
  edges and resolved entity nodes until that job commits. None
  writes untagged, for callers outside a job.
- **tracer** (<code>Tracer | None</code>) – Passed to description summarization.

**Raises:**

- <code>ValueError</code> – No decisions are supplied, or a decision references a
  member outside the supplied component.

### `agrag.ingestion.settings` \{#agrag-ingestion-settings}

Configuration for the Cutover Job crash-recovery machine.

**Classes:**

- [**CutoverJobSettings**](#agrag-ingestion-settings-CutoverJobSettings) – Configuration for the Cutover Job crash-recovery machine.

#### `agrag.ingestion.settings.CutoverJobSettings` \{#agrag-ingestion-settings-CutoverJobSettings}

Bases: <code>BaseSettings</code>

Configuration for the Cutover Job crash-recovery machine.

**Attributes:**

- [**lease_ttl_seconds**](#agrag-ingestion-settings-CutoverJobSettings-lease_ttl_seconds) (<code>int</code>) – How long a worker's lease is valid before another
  worker may steal it. Env: CUTOVER_JOB_LEASE_TTL_SECONDS.

Env prefix: `CUTOVER_JOB_`.

##### `agrag.ingestion.settings.CutoverJobSettings.lease_ttl_seconds` \{#agrag-ingestion-settings-CutoverJobSettings-lease_ttl_seconds}

```python
lease_ttl_seconds: int = Field(default=60, gt=0)
```

##### `agrag.ingestion.settings.CutoverJobSettings.model_config` \{#agrag-ingestion-settings-CutoverJobSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='CUTOVER_JOB_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

### `agrag.ingestion.stats` \{#agrag-ingestion-stats}

Per-stage observability types for the ingestion pipeline.

One class per module under this package; this init re-exports them so
`from agrag.ingestion.stats import ExtractionStats` keeps working.
`StageFailure`/`CappedFailures`/`cap_failures`/`MAX_FAILURES_PER_STAGE`
live in `agrag.common.data_models.stage_failure` -- a shared model used
outside the ingestion pipeline too -- and are not re-exported here.

**Modules:**

- [**chunking**](#agrag-ingestion-stats-chunking) – Chunking-stage stats.
- [**extraction**](#agrag-ingestion-stats-extraction) – Extraction-stage stats.
- [**ingest**](#agrag-ingestion-stats-ingest) – Ingestion-stage stats.
- [**merge**](#agrag-ingestion-stats-merge) – Merge-stage stats.
- [**resolution**](#agrag-ingestion-stats-resolution) – Resolution-stage stats.
- [**storage**](#agrag-ingestion-stats-storage) – Storage-write-stage stats.

**Classes:**

- [**ChunkingMatch**](#agrag-ingestion-stats-ChunkingMatch) – The chunker that one document got, and what it produced.
- [**ChunkingStats**](#agrag-ingestion-stats-ChunkingStats) – Chunking-stage results.
- [**ExtractionStats**](#agrag-ingestion-stats-ExtractionStats) – Extraction-stage results.
- [**IngestStats**](#agrag-ingestion-stats-IngestStats) – Ingestion-stage results.
- [**MergeStats**](#agrag-ingestion-stats-MergeStats) – Merge-stage results.
- [**ResolutionStats**](#agrag-ingestion-stats-ResolutionStats) – Resolution-stage results.
- [**StorageStats**](#agrag-ingestion-stats-StorageStats) – Storage-write-stage results.

#### `agrag.ingestion.stats.ChunkingMatch` \{#agrag-ingestion-stats-ChunkingMatch}

Bases: <code>BaseModel</code>

The chunker that one document got, and what it produced.

**Attributes:**

- [**document_key**](#agrag-ingestion-stats-ChunkingMatch-document_key) (<code>str</code>) – The key of the chunked document.
- [**rule**](#agrag-ingestion-stats-ChunkingMatch-rule) (<code>int | None</code>) – The index of the matching rule, or `None` for the fallback.
- [**strategy**](#agrag-ingestion-stats-ChunkingMatch-strategy) (<code>str</code>) – The strategy name of the chunker.
- [**chunker_hash**](#agrag-ingestion-stats-ChunkingMatch-chunker_hash) (<code>str</code>) – The fingerprint of the chunker settings.
- [**chunks**](#agrag-ingestion-stats-ChunkingMatch-chunks) (<code>int</code>) – The number of chunks the chunker produced.
- [**chunks_by_chunker**](#agrag-ingestion-stats-ChunkingMatch-chunks_by_chunker) (<code>dict\[str, int\]</code>) – Chunk counts per chunker name. A strategy that hands a
  part to a fallback names those chunks `<strategy>:<fallback>`, so this
  can hold more than one name. Empty means every chunk has `strategy`.

##### `agrag.ingestion.stats.ChunkingMatch.chunker_hash` \{#agrag-ingestion-stats-ChunkingMatch-chunker_hash}

```python
chunker_hash: str
```

##### `agrag.ingestion.stats.ChunkingMatch.chunks` \{#agrag-ingestion-stats-ChunkingMatch-chunks}

```python
chunks: int
```

##### `agrag.ingestion.stats.ChunkingMatch.chunks_by_chunker` \{#agrag-ingestion-stats-ChunkingMatch-chunks_by_chunker}

```python
chunks_by_chunker: dict[str, int] = Field(default_factory=dict)
```

##### `agrag.ingestion.stats.ChunkingMatch.document_key` \{#agrag-ingestion-stats-ChunkingMatch-document_key}

```python
document_key: str
```

##### `agrag.ingestion.stats.ChunkingMatch.rule` \{#agrag-ingestion-stats-ChunkingMatch-rule}

```python
rule: int | None
```

##### `agrag.ingestion.stats.ChunkingMatch.strategy` \{#agrag-ingestion-stats-ChunkingMatch-strategy}

```python
strategy: str
```

#### `agrag.ingestion.stats.ChunkingStats` \{#agrag-ingestion-stats-ChunkingStats}

Bases: <code>BaseModel</code>

Chunking-stage results.

**Attributes:**

- [**chunks_by_strategy**](#agrag-ingestion-stats-ChunkingStats-chunks_by_strategy) (<code>dict\[str, int\]</code>) – Chunk counts per chunker name, so chunks that a fallback
  made are counted under `<strategy>:<fallback>`.
- [**documents_by_rule**](#agrag-ingestion-stats-ChunkingStats-documents_by_rule) (<code>dict\[str, int\]</code>) – Document counts per rule, keyed `"rule 0"`,
  `"rule 1"` and so on, and `"fallback"`.
- [**matches**](#agrag-ingestion-stats-ChunkingStats-matches) (<code>list\[[ChunkingMatch](#agrag-ingestion-stats-chunking-ChunkingMatch)\]</code>) – One entry per chunked document, capped at 1000.
- [**matches_total**](#agrag-ingestion-stats-ChunkingStats-matches_total) (<code>int</code>) – Matches recorded before capping.
- [**matches_truncated**](#agrag-ingestion-stats-ChunkingStats-matches_truncated) (<code>bool</code>) – Whether `matches` was cut to the cap.

**Functions:**

- [**from_matches**](#agrag-ingestion-stats-ChunkingStats-from_matches) – Summarize per-document matches.

##### `agrag.ingestion.stats.ChunkingStats.chunks_by_strategy` \{#agrag-ingestion-stats-ChunkingStats-chunks_by_strategy}

```python
chunks_by_strategy: dict[str, int] = Field(default_factory=dict)
```

##### `agrag.ingestion.stats.ChunkingStats.documents_by_rule` \{#agrag-ingestion-stats-ChunkingStats-documents_by_rule}

```python
documents_by_rule: dict[str, int] = Field(default_factory=dict)
```

##### `agrag.ingestion.stats.ChunkingStats.from_matches` \{#agrag-ingestion-stats-ChunkingStats-from_matches}

```python
from_matches(matches:list[ChunkingMatch]) -> ChunkingStats
```

Summarize per-document matches.

**Parameters:**

- **matches** (<code>list\[[ChunkingMatch](#agrag-ingestion-stats-chunking-ChunkingMatch)\]</code>) – One match per chunked document, in chunking order.

**Returns:**

- <code>[ChunkingStats](#agrag-ingestion-stats-chunking-ChunkingStats)</code> – The counters over all matches and the matches up to the cap.

##### `agrag.ingestion.stats.ChunkingStats.matches` \{#agrag-ingestion-stats-ChunkingStats-matches}

```python
matches: list[ChunkingMatch] = Field(default_factory=list)
```

##### `agrag.ingestion.stats.ChunkingStats.matches_total` \{#agrag-ingestion-stats-ChunkingStats-matches_total}

```python
matches_total: int = 0
```

##### `agrag.ingestion.stats.ChunkingStats.matches_truncated` \{#agrag-ingestion-stats-ChunkingStats-matches_truncated}

```python
matches_truncated: bool = False
```

#### `agrag.ingestion.stats.ExtractionStats` \{#agrag-ingestion-stats-ExtractionStats}

Bases: <code>BaseModel</code>

Extraction-stage results.

**Attributes:**

- [**chunks_processed**](#agrag-ingestion-stats-ExtractionStats-chunks_processed) (<code>int</code>) – Chunks the stage ran the extractor on.
- [**entities_extracted**](#agrag-ingestion-stats-ExtractionStats-entities_extracted) (<code>int</code>) – Entities the extractor returned.
- [**relations_extracted**](#agrag-ingestion-stats-ExtractionStats-relations_extracted) (<code>int</code>) – Relations the extractor returned.
- [**failures**](#agrag-ingestion-stats-ExtractionStats-failures) (<code>list\[[StageFailure](common.md#agrag-common-data_models-stage_failure-StageFailure)\]</code>) – Per-item failures, capped per call.
- [**failures_total**](#agrag-ingestion-stats-ExtractionStats-failures_total) (<code>int</code>) – Failures recorded before capping.
- [**failures_truncated**](#agrag-ingestion-stats-ExtractionStats-failures_truncated) (<code>bool</code>) – Whether `failures` was cut to the cap.

##### `agrag.ingestion.stats.ExtractionStats.chunks_processed` \{#agrag-ingestion-stats-ExtractionStats-chunks_processed}

```python
chunks_processed: int = 0
```

##### `agrag.ingestion.stats.ExtractionStats.entities_extracted` \{#agrag-ingestion-stats-ExtractionStats-entities_extracted}

```python
entities_extracted: int = 0
```

##### `agrag.ingestion.stats.ExtractionStats.failures` \{#agrag-ingestion-stats-ExtractionStats-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

##### `agrag.ingestion.stats.ExtractionStats.failures_total` \{#agrag-ingestion-stats-ExtractionStats-failures_total}

```python
failures_total: int = 0
```

##### `agrag.ingestion.stats.ExtractionStats.failures_truncated` \{#agrag-ingestion-stats-ExtractionStats-failures_truncated}

```python
failures_truncated: bool = False
```

##### `agrag.ingestion.stats.ExtractionStats.relations_extracted` \{#agrag-ingestion-stats-ExtractionStats-relations_extracted}

```python
relations_extracted: int = 0
```

#### `agrag.ingestion.stats.IngestStats` \{#agrag-ingestion-stats-IngestStats}

Bases: <code>BaseModel</code>

Ingestion-stage results.

**Attributes:**

- [**documents**](#agrag-ingestion-stats-IngestStats-documents) (<code>int</code>) –
- [**quarantined**](#agrag-ingestion-stats-IngestStats-quarantined) (<code>int</code>) –
- [**quarantined_items**](#agrag-ingestion-stats-IngestStats-quarantined_items) (<code>list\[[StageFailure](common.md#agrag-common-data_models-stage_failure-StageFailure)\]</code>) –
- [**skipped**](#agrag-ingestion-stats-IngestStats-skipped) (<code>int</code>) –
- [**sources**](#agrag-ingestion-stats-IngestStats-sources) (<code>int</code>) –

##### `agrag.ingestion.stats.IngestStats.documents` \{#agrag-ingestion-stats-IngestStats-documents}

```python
documents: int = 0
```

##### `agrag.ingestion.stats.IngestStats.quarantined` \{#agrag-ingestion-stats-IngestStats-quarantined}

```python
quarantined: int = 0
```

##### `agrag.ingestion.stats.IngestStats.quarantined_items` \{#agrag-ingestion-stats-IngestStats-quarantined_items}

```python
quarantined_items: list[StageFailure] = Field(default_factory=list)
```

##### `agrag.ingestion.stats.IngestStats.skipped` \{#agrag-ingestion-stats-IngestStats-skipped}

```python
skipped: int = 0
```

##### `agrag.ingestion.stats.IngestStats.sources` \{#agrag-ingestion-stats-IngestStats-sources}

```python
sources: int = 0
```

#### `agrag.ingestion.stats.MergeStats` \{#agrag-ingestion-stats-MergeStats}

Bases: <code>BaseModel</code>

Merge-stage results.

**Attributes:**

- [**nodes_created**](#agrag-ingestion-stats-MergeStats-nodes_created) (<code>int</code>) – Brand-new entities created this call.
- [**nodes_updated**](#agrag-ingestion-stats-MergeStats-nodes_updated) (<code>int</code>) – Existing entities that absorbed new mention data.
- [**conflicts_resolved**](#agrag-ingestion-stats-MergeStats-conflicts_resolved) (<code>int</code>) – Total property/description conflicts resolved
  across every merge this call performed.
- [**failures**](#agrag-ingestion-stats-MergeStats-failures) (<code>list\[[StageFailure](common.md#agrag-common-data_models-stage_failure-StageFailure)\]</code>) – Includes an LLM failure during description
  summarization. The merge still falls back to concatenation and
  completes, but the failure is recorded here.
- [**failures_total**](#agrag-ingestion-stats-MergeStats-failures_total) (<code>int</code>) – Failures recorded before capping.
- [**failures_truncated**](#agrag-ingestion-stats-MergeStats-failures_truncated) (<code>bool</code>) – Whether `failures` was cut to the cap.

##### `agrag.ingestion.stats.MergeStats.conflicts_resolved` \{#agrag-ingestion-stats-MergeStats-conflicts_resolved}

```python
conflicts_resolved: int = 0
```

##### `agrag.ingestion.stats.MergeStats.failures` \{#agrag-ingestion-stats-MergeStats-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

##### `agrag.ingestion.stats.MergeStats.failures_total` \{#agrag-ingestion-stats-MergeStats-failures_total}

```python
failures_total: int = 0
```

##### `agrag.ingestion.stats.MergeStats.failures_truncated` \{#agrag-ingestion-stats-MergeStats-failures_truncated}

```python
failures_truncated: bool = False
```

##### `agrag.ingestion.stats.MergeStats.nodes_created` \{#agrag-ingestion-stats-MergeStats-nodes_created}

```python
nodes_created: int = 0
```

##### `agrag.ingestion.stats.MergeStats.nodes_updated` \{#agrag-ingestion-stats-MergeStats-nodes_updated}

```python
nodes_updated: int = 0
```

#### `agrag.ingestion.stats.ResolutionStats` \{#agrag-ingestion-stats-ResolutionStats}

Bases: <code>BaseModel</code>

Resolution-stage results.

**Attributes:**

- [**exact_match_hits**](#agrag-ingestion-stats-ResolutionStats-exact_match_hits) (<code>int</code>) – Mentions that matched an already-persisted
  entity via the global exact-match tier.
- [**in_batch_groups**](#agrag-ingestion-stats-ResolutionStats-in_batch_groups) (<code>int</code>) – Resolution groups the in-batch fuzzy/LLM tier
  found.
- [**ambiguous_count**](#agrag-ingestion-stats-ResolutionStats-ambiguous_count) (<code>int</code>) – Comparisons no comparator could confidently
  decide. These pairs are never merged.

##### `agrag.ingestion.stats.ResolutionStats.ambiguous_count` \{#agrag-ingestion-stats-ResolutionStats-ambiguous_count}

```python
ambiguous_count: int = 0
```

##### `agrag.ingestion.stats.ResolutionStats.exact_match_hits` \{#agrag-ingestion-stats-ResolutionStats-exact_match_hits}

```python
exact_match_hits: int = 0
```

##### `agrag.ingestion.stats.ResolutionStats.in_batch_groups` \{#agrag-ingestion-stats-ResolutionStats-in_batch_groups}

```python
in_batch_groups: int = 0
```

#### `agrag.ingestion.stats.StorageStats` \{#agrag-ingestion-stats-StorageStats}

Bases: <code>BaseModel</code>

Storage-write-stage results.

**Attributes:**

- [**nodes_written**](#agrag-ingestion-stats-StorageStats-nodes_written) (<code>int</code>) – Chunk and Entity nodes together, one aggregate
  count rather than a sub-count per kind — both are written in
  the same final phase, so there is one natural accounting
  point.
- [**relationships_written**](#agrag-ingestion-stats-StorageStats-relationships_written) (<code>int</code>) – Domain Relation and MENTIONED_IN edges
  together, for the same reason.
- [**failures**](#agrag-ingestion-stats-StorageStats-failures) (<code>list\[[StageFailure](common.md#agrag-common-data_models-stage_failure-StageFailure)\]</code>) – Isolated graph-write failures are reported per record and
  capped per call. Conversion, embedding, vector-store, and other
  non-isolatable graph failures can use one stage-level failure.
  The counts include only records that landed.
- [**failures_total**](#agrag-ingestion-stats-StorageStats-failures_total) (<code>int</code>) – Failures recorded before capping.
- [**failures_truncated**](#agrag-ingestion-stats-StorageStats-failures_truncated) (<code>bool</code>) – Whether `failures` was cut to the cap.

##### `agrag.ingestion.stats.StorageStats.failures` \{#agrag-ingestion-stats-StorageStats-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

##### `agrag.ingestion.stats.StorageStats.failures_total` \{#agrag-ingestion-stats-StorageStats-failures_total}

```python
failures_total: int = 0
```

##### `agrag.ingestion.stats.StorageStats.failures_truncated` \{#agrag-ingestion-stats-StorageStats-failures_truncated}

```python
failures_truncated: bool = False
```

##### `agrag.ingestion.stats.StorageStats.nodes_written` \{#agrag-ingestion-stats-StorageStats-nodes_written}

```python
nodes_written: int = 0
```

##### `agrag.ingestion.stats.StorageStats.relationships_written` \{#agrag-ingestion-stats-StorageStats-relationships_written}

```python
relationships_written: int = 0
```

#### `agrag.ingestion.stats.chunking` \{#agrag-ingestion-stats-chunking}

Chunking-stage stats.

**Classes:**

- [**ChunkingMatch**](#agrag-ingestion-stats-chunking-ChunkingMatch) – The chunker that one document got, and what it produced.
- [**ChunkingStats**](#agrag-ingestion-stats-chunking-ChunkingStats) – Chunking-stage results.

**Attributes:**

- [**MAX_CHUNKING_MATCHES**](#agrag-ingestion-stats-chunking-MAX_CHUNKING_MATCHES) –

##### `agrag.ingestion.stats.chunking.ChunkingMatch` \{#agrag-ingestion-stats-chunking-ChunkingMatch}

Bases: <code>BaseModel</code>

The chunker that one document got, and what it produced.

**Attributes:**

- [**document_key**](#agrag-ingestion-stats-chunking-ChunkingMatch-document_key) (<code>str</code>) – The key of the chunked document.
- [**rule**](#agrag-ingestion-stats-chunking-ChunkingMatch-rule) (<code>int | None</code>) – The index of the matching rule, or `None` for the fallback.
- [**strategy**](#agrag-ingestion-stats-chunking-ChunkingMatch-strategy) (<code>str</code>) – The strategy name of the chunker.
- [**chunker_hash**](#agrag-ingestion-stats-chunking-ChunkingMatch-chunker_hash) (<code>str</code>) – The fingerprint of the chunker settings.
- [**chunks**](#agrag-ingestion-stats-chunking-ChunkingMatch-chunks) (<code>int</code>) – The number of chunks the chunker produced.
- [**chunks_by_chunker**](#agrag-ingestion-stats-chunking-ChunkingMatch-chunks_by_chunker) (<code>dict\[str, int\]</code>) – Chunk counts per chunker name. A strategy that hands a
  part to a fallback names those chunks `<strategy>:<fallback>`, so this
  can hold more than one name. Empty means every chunk has `strategy`.

###### `agrag.ingestion.stats.chunking.ChunkingMatch.chunker_hash` \{#agrag-ingestion-stats-chunking-ChunkingMatch-chunker_hash}

```python
chunker_hash: str
```

###### `agrag.ingestion.stats.chunking.ChunkingMatch.chunks` \{#agrag-ingestion-stats-chunking-ChunkingMatch-chunks}

```python
chunks: int
```

###### `agrag.ingestion.stats.chunking.ChunkingMatch.chunks_by_chunker` \{#agrag-ingestion-stats-chunking-ChunkingMatch-chunks_by_chunker}

```python
chunks_by_chunker: dict[str, int] = Field(default_factory=dict)
```

###### `agrag.ingestion.stats.chunking.ChunkingMatch.document_key` \{#agrag-ingestion-stats-chunking-ChunkingMatch-document_key}

```python
document_key: str
```

###### `agrag.ingestion.stats.chunking.ChunkingMatch.rule` \{#agrag-ingestion-stats-chunking-ChunkingMatch-rule}

```python
rule: int | None
```

###### `agrag.ingestion.stats.chunking.ChunkingMatch.strategy` \{#agrag-ingestion-stats-chunking-ChunkingMatch-strategy}

```python
strategy: str
```

##### `agrag.ingestion.stats.chunking.ChunkingStats` \{#agrag-ingestion-stats-chunking-ChunkingStats}

Bases: <code>BaseModel</code>

Chunking-stage results.

**Attributes:**

- [**chunks_by_strategy**](#agrag-ingestion-stats-chunking-ChunkingStats-chunks_by_strategy) (<code>dict\[str, int\]</code>) – Chunk counts per chunker name, so chunks that a fallback
  made are counted under `<strategy>:<fallback>`.
- [**documents_by_rule**](#agrag-ingestion-stats-chunking-ChunkingStats-documents_by_rule) (<code>dict\[str, int\]</code>) – Document counts per rule, keyed `"rule 0"`,
  `"rule 1"` and so on, and `"fallback"`.
- [**matches**](#agrag-ingestion-stats-chunking-ChunkingStats-matches) (<code>list\[[ChunkingMatch](#agrag-ingestion-stats-chunking-ChunkingMatch)\]</code>) – One entry per chunked document, capped at 1000.
- [**matches_total**](#agrag-ingestion-stats-chunking-ChunkingStats-matches_total) (<code>int</code>) – Matches recorded before capping.
- [**matches_truncated**](#agrag-ingestion-stats-chunking-ChunkingStats-matches_truncated) (<code>bool</code>) – Whether `matches` was cut to the cap.

**Functions:**

- [**from_matches**](#agrag-ingestion-stats-chunking-ChunkingStats-from_matches) – Summarize per-document matches.

###### `agrag.ingestion.stats.chunking.ChunkingStats.chunks_by_strategy` \{#agrag-ingestion-stats-chunking-ChunkingStats-chunks_by_strategy}

```python
chunks_by_strategy: dict[str, int] = Field(default_factory=dict)
```

###### `agrag.ingestion.stats.chunking.ChunkingStats.documents_by_rule` \{#agrag-ingestion-stats-chunking-ChunkingStats-documents_by_rule}

```python
documents_by_rule: dict[str, int] = Field(default_factory=dict)
```

###### `agrag.ingestion.stats.chunking.ChunkingStats.from_matches` \{#agrag-ingestion-stats-chunking-ChunkingStats-from_matches}

```python
from_matches(matches:list[ChunkingMatch]) -> ChunkingStats
```

Summarize per-document matches.

**Parameters:**

- **matches** (<code>list\[[ChunkingMatch](#agrag-ingestion-stats-chunking-ChunkingMatch)\]</code>) – One match per chunked document, in chunking order.

**Returns:**

- <code>[ChunkingStats](#agrag-ingestion-stats-chunking-ChunkingStats)</code> – The counters over all matches and the matches up to the cap.

###### `agrag.ingestion.stats.chunking.ChunkingStats.matches` \{#agrag-ingestion-stats-chunking-ChunkingStats-matches}

```python
matches: list[ChunkingMatch] = Field(default_factory=list)
```

###### `agrag.ingestion.stats.chunking.ChunkingStats.matches_total` \{#agrag-ingestion-stats-chunking-ChunkingStats-matches_total}

```python
matches_total: int = 0
```

###### `agrag.ingestion.stats.chunking.ChunkingStats.matches_truncated` \{#agrag-ingestion-stats-chunking-ChunkingStats-matches_truncated}

```python
matches_truncated: bool = False
```

##### `agrag.ingestion.stats.chunking.MAX_CHUNKING_MATCHES` \{#agrag-ingestion-stats-chunking-MAX_CHUNKING_MATCHES}

```python
MAX_CHUNKING_MATCHES = 1000
```

#### `agrag.ingestion.stats.extraction` \{#agrag-ingestion-stats-extraction}

Extraction-stage stats.

**Classes:**

- [**ExtractionStats**](#agrag-ingestion-stats-extraction-ExtractionStats) – Extraction-stage results.

##### `agrag.ingestion.stats.extraction.ExtractionStats` \{#agrag-ingestion-stats-extraction-ExtractionStats}

Bases: <code>BaseModel</code>

Extraction-stage results.

**Attributes:**

- [**chunks_processed**](#agrag-ingestion-stats-extraction-ExtractionStats-chunks_processed) (<code>int</code>) – Chunks the stage ran the extractor on.
- [**entities_extracted**](#agrag-ingestion-stats-extraction-ExtractionStats-entities_extracted) (<code>int</code>) – Entities the extractor returned.
- [**relations_extracted**](#agrag-ingestion-stats-extraction-ExtractionStats-relations_extracted) (<code>int</code>) – Relations the extractor returned.
- [**failures**](#agrag-ingestion-stats-extraction-ExtractionStats-failures) (<code>list\[[StageFailure](common.md#agrag-common-data_models-stage_failure-StageFailure)\]</code>) – Per-item failures, capped per call.
- [**failures_total**](#agrag-ingestion-stats-extraction-ExtractionStats-failures_total) (<code>int</code>) – Failures recorded before capping.
- [**failures_truncated**](#agrag-ingestion-stats-extraction-ExtractionStats-failures_truncated) (<code>bool</code>) – Whether `failures` was cut to the cap.

###### `agrag.ingestion.stats.extraction.ExtractionStats.chunks_processed` \{#agrag-ingestion-stats-extraction-ExtractionStats-chunks_processed}

```python
chunks_processed: int = 0
```

###### `agrag.ingestion.stats.extraction.ExtractionStats.entities_extracted` \{#agrag-ingestion-stats-extraction-ExtractionStats-entities_extracted}

```python
entities_extracted: int = 0
```

###### `agrag.ingestion.stats.extraction.ExtractionStats.failures` \{#agrag-ingestion-stats-extraction-ExtractionStats-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

###### `agrag.ingestion.stats.extraction.ExtractionStats.failures_total` \{#agrag-ingestion-stats-extraction-ExtractionStats-failures_total}

```python
failures_total: int = 0
```

###### `agrag.ingestion.stats.extraction.ExtractionStats.failures_truncated` \{#agrag-ingestion-stats-extraction-ExtractionStats-failures_truncated}

```python
failures_truncated: bool = False
```

###### `agrag.ingestion.stats.extraction.ExtractionStats.relations_extracted` \{#agrag-ingestion-stats-extraction-ExtractionStats-relations_extracted}

```python
relations_extracted: int = 0
```

#### `agrag.ingestion.stats.ingest` \{#agrag-ingestion-stats-ingest}

Ingestion-stage stats.

**Classes:**

- [**IngestStats**](#agrag-ingestion-stats-ingest-IngestStats) – Ingestion-stage results.

##### `agrag.ingestion.stats.ingest.IngestStats` \{#agrag-ingestion-stats-ingest-IngestStats}

Bases: <code>BaseModel</code>

Ingestion-stage results.

**Attributes:**

- [**documents**](#agrag-ingestion-stats-ingest-IngestStats-documents) (<code>int</code>) –
- [**quarantined**](#agrag-ingestion-stats-ingest-IngestStats-quarantined) (<code>int</code>) –
- [**quarantined_items**](#agrag-ingestion-stats-ingest-IngestStats-quarantined_items) (<code>list\[[StageFailure](common.md#agrag-common-data_models-stage_failure-StageFailure)\]</code>) –
- [**skipped**](#agrag-ingestion-stats-ingest-IngestStats-skipped) (<code>int</code>) –
- [**sources**](#agrag-ingestion-stats-ingest-IngestStats-sources) (<code>int</code>) –

###### `agrag.ingestion.stats.ingest.IngestStats.documents` \{#agrag-ingestion-stats-ingest-IngestStats-documents}

```python
documents: int = 0
```

###### `agrag.ingestion.stats.ingest.IngestStats.quarantined` \{#agrag-ingestion-stats-ingest-IngestStats-quarantined}

```python
quarantined: int = 0
```

###### `agrag.ingestion.stats.ingest.IngestStats.quarantined_items` \{#agrag-ingestion-stats-ingest-IngestStats-quarantined_items}

```python
quarantined_items: list[StageFailure] = Field(default_factory=list)
```

###### `agrag.ingestion.stats.ingest.IngestStats.skipped` \{#agrag-ingestion-stats-ingest-IngestStats-skipped}

```python
skipped: int = 0
```

###### `agrag.ingestion.stats.ingest.IngestStats.sources` \{#agrag-ingestion-stats-ingest-IngestStats-sources}

```python
sources: int = 0
```

#### `agrag.ingestion.stats.merge` \{#agrag-ingestion-stats-merge}

Merge-stage stats.

**Classes:**

- [**MergeStats**](#agrag-ingestion-stats-merge-MergeStats) – Merge-stage results.

##### `agrag.ingestion.stats.merge.MergeStats` \{#agrag-ingestion-stats-merge-MergeStats}

Bases: <code>BaseModel</code>

Merge-stage results.

**Attributes:**

- [**nodes_created**](#agrag-ingestion-stats-merge-MergeStats-nodes_created) (<code>int</code>) – Brand-new entities created this call.
- [**nodes_updated**](#agrag-ingestion-stats-merge-MergeStats-nodes_updated) (<code>int</code>) – Existing entities that absorbed new mention data.
- [**conflicts_resolved**](#agrag-ingestion-stats-merge-MergeStats-conflicts_resolved) (<code>int</code>) – Total property/description conflicts resolved
  across every merge this call performed.
- [**failures**](#agrag-ingestion-stats-merge-MergeStats-failures) (<code>list\[[StageFailure](common.md#agrag-common-data_models-stage_failure-StageFailure)\]</code>) – Includes an LLM failure during description
  summarization. The merge still falls back to concatenation and
  completes, but the failure is recorded here.
- [**failures_total**](#agrag-ingestion-stats-merge-MergeStats-failures_total) (<code>int</code>) – Failures recorded before capping.
- [**failures_truncated**](#agrag-ingestion-stats-merge-MergeStats-failures_truncated) (<code>bool</code>) – Whether `failures` was cut to the cap.

###### `agrag.ingestion.stats.merge.MergeStats.conflicts_resolved` \{#agrag-ingestion-stats-merge-MergeStats-conflicts_resolved}

```python
conflicts_resolved: int = 0
```

###### `agrag.ingestion.stats.merge.MergeStats.failures` \{#agrag-ingestion-stats-merge-MergeStats-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

###### `agrag.ingestion.stats.merge.MergeStats.failures_total` \{#agrag-ingestion-stats-merge-MergeStats-failures_total}

```python
failures_total: int = 0
```

###### `agrag.ingestion.stats.merge.MergeStats.failures_truncated` \{#agrag-ingestion-stats-merge-MergeStats-failures_truncated}

```python
failures_truncated: bool = False
```

###### `agrag.ingestion.stats.merge.MergeStats.nodes_created` \{#agrag-ingestion-stats-merge-MergeStats-nodes_created}

```python
nodes_created: int = 0
```

###### `agrag.ingestion.stats.merge.MergeStats.nodes_updated` \{#agrag-ingestion-stats-merge-MergeStats-nodes_updated}

```python
nodes_updated: int = 0
```

#### `agrag.ingestion.stats.resolution` \{#agrag-ingestion-stats-resolution}

Resolution-stage stats.

**Classes:**

- [**ResolutionStats**](#agrag-ingestion-stats-resolution-ResolutionStats) – Resolution-stage results.

##### `agrag.ingestion.stats.resolution.ResolutionStats` \{#agrag-ingestion-stats-resolution-ResolutionStats}

Bases: <code>BaseModel</code>

Resolution-stage results.

**Attributes:**

- [**exact_match_hits**](#agrag-ingestion-stats-resolution-ResolutionStats-exact_match_hits) (<code>int</code>) – Mentions that matched an already-persisted
  entity via the global exact-match tier.
- [**in_batch_groups**](#agrag-ingestion-stats-resolution-ResolutionStats-in_batch_groups) (<code>int</code>) – Resolution groups the in-batch fuzzy/LLM tier
  found.
- [**ambiguous_count**](#agrag-ingestion-stats-resolution-ResolutionStats-ambiguous_count) (<code>int</code>) – Comparisons no comparator could confidently
  decide. These pairs are never merged.

###### `agrag.ingestion.stats.resolution.ResolutionStats.ambiguous_count` \{#agrag-ingestion-stats-resolution-ResolutionStats-ambiguous_count}

```python
ambiguous_count: int = 0
```

###### `agrag.ingestion.stats.resolution.ResolutionStats.exact_match_hits` \{#agrag-ingestion-stats-resolution-ResolutionStats-exact_match_hits}

```python
exact_match_hits: int = 0
```

###### `agrag.ingestion.stats.resolution.ResolutionStats.in_batch_groups` \{#agrag-ingestion-stats-resolution-ResolutionStats-in_batch_groups}

```python
in_batch_groups: int = 0
```

#### `agrag.ingestion.stats.storage` \{#agrag-ingestion-stats-storage}

Storage-write-stage stats.

**Classes:**

- [**StorageStats**](#agrag-ingestion-stats-storage-StorageStats) – Storage-write-stage results.

##### `agrag.ingestion.stats.storage.StorageStats` \{#agrag-ingestion-stats-storage-StorageStats}

Bases: <code>BaseModel</code>

Storage-write-stage results.

**Attributes:**

- [**nodes_written**](#agrag-ingestion-stats-storage-StorageStats-nodes_written) (<code>int</code>) – Chunk and Entity nodes together, one aggregate
  count rather than a sub-count per kind — both are written in
  the same final phase, so there is one natural accounting
  point.
- [**relationships_written**](#agrag-ingestion-stats-storage-StorageStats-relationships_written) (<code>int</code>) – Domain Relation and MENTIONED_IN edges
  together, for the same reason.
- [**failures**](#agrag-ingestion-stats-storage-StorageStats-failures) (<code>list\[[StageFailure](common.md#agrag-common-data_models-stage_failure-StageFailure)\]</code>) – Isolated graph-write failures are reported per record and
  capped per call. Conversion, embedding, vector-store, and other
  non-isolatable graph failures can use one stage-level failure.
  The counts include only records that landed.
- [**failures_total**](#agrag-ingestion-stats-storage-StorageStats-failures_total) (<code>int</code>) – Failures recorded before capping.
- [**failures_truncated**](#agrag-ingestion-stats-storage-StorageStats-failures_truncated) (<code>bool</code>) – Whether `failures` was cut to the cap.

###### `agrag.ingestion.stats.storage.StorageStats.failures` \{#agrag-ingestion-stats-storage-StorageStats-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

###### `agrag.ingestion.stats.storage.StorageStats.failures_total` \{#agrag-ingestion-stats-storage-StorageStats-failures_total}

```python
failures_total: int = 0
```

###### `agrag.ingestion.stats.storage.StorageStats.failures_truncated` \{#agrag-ingestion-stats-storage-StorageStats-failures_truncated}

```python
failures_truncated: bool = False
```

###### `agrag.ingestion.stats.storage.StorageStats.nodes_written` \{#agrag-ingestion-stats-storage-StorageStats-nodes_written}

```python
nodes_written: int = 0
```

###### `agrag.ingestion.stats.storage.StorageStats.relationships_written` \{#agrag-ingestion-stats-storage-StorageStats-relationships_written}

```python
relationships_written: int = 0
```
