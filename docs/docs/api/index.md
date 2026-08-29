---
title: API Reference
sidebar_position: 2
---

## `agrag`

Agentic GraphRAG: graph-based RAG with agentic reasoning.

**Modules:**

- [**chunking**](#agrag.chunking) – Chunking helpers for the ingestion layer.
- [**cypher**](#agrag.cypher) – Cypher query builders for graph stores.
- [**embedding**](#agrag.embedding) – Text embedding: turn strings into dense vectors.
- [**graphdb**](#agrag.graphdb) – Graph storage backends and the build shortcut.
- [**ingestion**](#agrag.ingestion) – The ingestion package.
- [**observability**](#agrag.observability) – OpenTelemetry wiring for the ingestion layer.
- [**vectordb**](#agrag.vectordb) – Vector storage backends and the build shortcut.

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

### `agrag.cypher`

Cypher query builders for graph stores.

Leaf modules only: nothing here imports `agrag.graphdb`, so the dependency
points one way (store -> cypher).

**Modules:**

- [**entities**](#agrag.cypher.entities) – Cypher builders for node writes and filters.
- [**relations**](#agrag.cypher.relations) – Cypher builders for relationship writes.
- [**schema**](#agrag.cypher.schema) – Cypher builders for constraints and native vector indexes.

#### `agrag.cypher.entities`

Cypher builders for node writes and filters.

Leaf module: imports nothing from `agrag.graphdb` or other store packages, so
the dependency points one way (store -> cypher).

**Functions:**

- [**filter_clause**](#agrag.cypher.entities.filter_clause) – Build a Cypher WHERE clause and parameters from a flat-dict filter.
- [**upsert_node_query**](#agrag.cypher.entities.upsert_node_query) – Build the Cypher for an UNWIND-batched node upsert.
- [**validate_identifier**](#agrag.cypher.entities.validate_identifier) – Check that a label or relationship type is a safe Cypher identifier.

##### `agrag.cypher.entities.filter_clause`

```python
filter_clause(filters:dict[str, Any], node_var:str = 'node') -> tuple[str, dict[str, Any]]
```

Build a Cypher WHERE clause and parameters from a flat-dict filter.

**Parameters:**

- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code>) – A flat-dict filter: a scalar value means exact match, a list
  value means any of, and all keys are AND-ed together.
- **node_var** (<code>[str](#str)</code>) – The Cypher variable bound to the node in the surrounding query.

**Returns:**

- <code>[str](#str)</code> – The `WHERE` clause text (beginning with `WHERE` when `filters` is
- <code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code> – non-empty, otherwise an empty string) and the parameter dict to pass
- <code>[tuple](#tuple)\[[str](#str), [dict](#dict)\[[str](#str), [Any](#typing.Any)\]\]</code> – with it.

##### `agrag.cypher.entities.upsert_node_query`

```python
upsert_node_query(label:str) -> str
```

Build the Cypher for an UNWIND-batched node upsert.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – A parameterized Cypher query expecting a `$records` list parameter.

##### `agrag.cypher.entities.validate_identifier`

```python
validate_identifier(value:str) -> str
```

Check that a label or relationship type is a safe Cypher identifier.

**Parameters:**

- **value** (<code>[str](#str)</code>) – The label or relationship type to check.

**Returns:**

- <code>[str](#str)</code> – `value` unchanged, once validated.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `value` is not a safe identifier.

#### `agrag.cypher.relations`

Cypher builders for relationship writes.

Leaf module: imports nothing from `agrag.graphdb`. See `entities.py` for the
identifier-validation contract shared by every Cypher builder.

**Functions:**

- [**upsert_relation_query**](#agrag.cypher.relations.upsert_relation_query) – Build the Cypher for an UNWIND-batched relationship upsert.

##### `agrag.cypher.relations.upsert_relation_query`

```python
upsert_relation_query(rel_type:str) -> str
```

Build the Cypher for an UNWIND-batched relationship upsert.

**Parameters:**

- **rel_type** (<code>[str](#str)</code>) – The relationship type. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – A parameterized Cypher query expecting a `$records` list parameter whose
- <code>[str](#str)</code> – items carry `start_id`, `end_id`, and `properties` keys.

#### `agrag.cypher.schema`

Cypher builders for constraints and native vector indexes.

Leaf module: imports nothing from `agrag.graphdb`. See `entities.py` for the
identifier-validation contract shared by every Cypher builder.

**Functions:**

- [**node_id_constraint_query**](#agrag.cypher.schema.node_id_constraint_query) – Build a CREATE CONSTRAINT query making `id` unique per node.
- [**plain_index_query**](#agrag.cypher.schema.plain_index_query) – Build a CREATE INDEX query on the node `id` property.
- [**vector_index_name**](#agrag.cypher.schema.vector_index_name) – Derive the deterministic name a vector index is created under.
- [**vector_index_query**](#agrag.cypher.schema.vector_index_query) – Build a CREATE VECTOR INDEX query for native vector search.
- [**vector_search_query**](#agrag.cypher.schema.vector_search_query) – Build a native vector search query and its filter parameters.

##### `agrag.cypher.schema.node_id_constraint_query`

```python
node_id_constraint_query(label:str) -> str
```

Build a CREATE CONSTRAINT query making `id` unique per node.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – A Cypher query creating the uniqueness constraint if absent.

##### `agrag.cypher.schema.plain_index_query`

```python
plain_index_query(label:str) -> str
```

Build a CREATE INDEX query on the node `id` property.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – A Cypher query creating the range index if absent.

##### `agrag.cypher.schema.vector_index_name`

```python
vector_index_name(label:str, vector_property:str) -> str
```

Derive the deterministic name a vector index is created under.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label. Must already be validated.
- **vector_property** (<code>[str](#str)</code>) – The vector property name. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – The index name `ensure_vector_index` and `vector_search` share.

##### `agrag.cypher.schema.vector_index_query`

```python
vector_index_query(label:str, vector_property:str, dimensions:int, distance:Distance) -> str
```

Build a CREATE VECTOR INDEX query for native vector search.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label. Must already be validated.
- **vector_property** (<code>[str](#str)</code>) – The vector property name. Must already be validated.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric, mapped to Neo4j's similarity function.

**Returns:**

- <code>[str](#str)</code> – A Cypher query creating the vector index if absent.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `distance` is not a metric Neo4j vector indexes support.

##### `agrag.cypher.schema.vector_search_query`

```python
vector_search_query(index_name:str, filters:dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]
```

Build a native vector search query and its filter parameters.

**Parameters:**

- **index_name** (<code>[str](#str)</code>) – The vector index name from `vector_index_name`.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – An optional flat-dict filter applied with `WHERE`.

**Returns:**

- <code>[str](#str)</code> – The Cypher query yielding `node` and `score`, and a parameter dict
- <code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code> – holding only the filter parameters (the caller adds `index`, `k`,
- <code>[tuple](#tuple)\[[str](#str), [dict](#dict)\[[str](#str), [Any](#typing.Any)\]\]</code> – and `vector`).

### `agrag.embedding`

Text embedding: turn strings into dense vectors.

**Modules:**

- [**base**](#agrag.embedding.base) – The Embedder and EmbeddingCache protocols.
- [**errors**](#agrag.embedding.errors) – Errors that the embedding layer raises.
- [**fastembed_bm25**](#agrag.embedding.fastembed_bm25) – BM25 sparse embedder backed by FastEmbed.
- [**sentence_transformers**](#agrag.embedding.sentence_transformers) – Sentence-transformers embedder implementation.
- [**settings**](#agrag.embedding.settings) – Settings for the sentence-transformers embedder.
- [**sparse_base**](#agrag.embedding.sparse_base) – Sparse lexical vectors and the sparse embedder protocol.

**Classes:**

- [**Embedder**](#agrag.embedding.Embedder) – A component that turns text into dense embedding vectors.
- [**EmbeddingSettings**](#agrag.embedding.EmbeddingSettings) – Sentence-transformers embedder configuration.
- [**FastEmbedBM25Embedder**](#agrag.embedding.FastEmbedBM25Embedder) – A sparse BM25 embedder built on FastEmbed.
- [**SentenceTransformerEmbedder**](#agrag.embedding.SentenceTransformerEmbedder) – An embedder backed by sentence-transformers.
- [**SparseEmbedder**](#agrag.embedding.SparseEmbedder) – A component that turns text into sparse lexical vectors, for hybrid search.
- [**SparseVector**](#agrag.embedding.SparseVector) – A sparse vector: nonzero indices and their values.

**Functions:**

- [**build_embedder**](#agrag.embedding.build_embedder) – Build an embedder from a model name, or return an embedder unchanged.

#### `agrag.embedding.Embedder`

Bases: <code>[ABC](#abc.ABC)</code>

A component that turns text into dense embedding vectors.

**Functions:**

- [**embed**](#agrag.embedding.Embedder.embed) – Embed a batch of texts.
- [**embed_one**](#agrag.embedding.Embedder.embed_one) – Embed a single text.

**Attributes:**

- [**dimensions**](#agrag.embedding.Embedder.dimensions) (<code>[int](#int)</code>) –
- [**model**](#agrag.embedding.Embedder.model) (<code>[str](#str)</code>) –

##### `agrag.embedding.Embedder.dimensions`

```python
dimensions: int
```

##### `agrag.embedding.Embedder.embed`

```python
embed(texts:Sequence[str]) -> list[list[float]]
```

Embed a batch of texts.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[list](#list)\[[float](#float)\]\]</code> – One vector per input text, in the same order.

##### `agrag.embedding.Embedder.embed_one`

```python
embed_one(text:str) -> list[float]
```

Embed a single text.

**Parameters:**

- **text** (<code>[str](#str)</code>) – The text to embed.

**Returns:**

- <code>[list](#list)\[[float](#float)\]</code> – The text's embedding vector.

##### `agrag.embedding.Embedder.model`

```python
model: str
```

#### `agrag.embedding.EmbeddingSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Sentence-transformers embedder configuration.

All fields are overridable via environment variables with the
`EMBEDDING_` prefix.

**Attributes:**

- [**model**](#agrag.embedding.EmbeddingSettings.model) (<code>[str](#str)</code>) – The sentence-transformers model name or path. Env: `EMBEDDING_MODEL`.
- [**device**](#agrag.embedding.EmbeddingSettings.device) (<code>[str](#str) | None</code>) – The device to load the model on, such as `"cpu"` or `"cuda"`.
  `None` uses sentence-transformers' own default detection. Env:
  `EMBEDDING_DEVICE`.
- [**normalize**](#agrag.embedding.EmbeddingSettings.normalize) (<code>[bool](#bool)</code>) – Whether to L2-normalize output vectors. Env: `EMBEDDING_NORMALIZE`.
- [**batch_size**](#agrag.embedding.EmbeddingSettings.batch_size) (<code>[int](#int)</code>) – The number of texts encoded per `model.encode` call. Env:
  `EMBEDDING_BATCH_SIZE`.
- [**cache_folder**](#agrag.embedding.EmbeddingSettings.cache_folder) (<code>[str](#str) | None</code>) – Where sentence-transformers caches downloaded models.
  `None` uses the library default. Env: `EMBEDDING_CACHE_FOLDER`.

##### `agrag.embedding.EmbeddingSettings.batch_size`

```python
batch_size: int = 32
```

##### `agrag.embedding.EmbeddingSettings.cache_folder`

```python
cache_folder: str | None = None
```

##### `agrag.embedding.EmbeddingSettings.device`

```python
device: str | None = None
```

##### `agrag.embedding.EmbeddingSettings.model`

```python
model: str = 'ibm-granite/granite-embedding-small-english-r2'
```

##### `agrag.embedding.EmbeddingSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='EMBEDDING_', env_file='.env', extra='ignore')
```

##### `agrag.embedding.EmbeddingSettings.normalize`

```python
normalize: bool = True
```

#### `agrag.embedding.FastEmbedBM25Embedder`

```python
FastEmbedBM25Embedder(*, model:str | None = None) -> None
```

Bases: <code>[SparseEmbedder](#agrag.embedding.sparse_base.SparseEmbedder)</code>

A sparse BM25 embedder built on FastEmbed.

The model loads lazily on first `embed`, so constructing the embedder
does not download weights. Each blocking call into FastEmbed runs in a
worker thread, keeping the event loop free. FastEmbed ships with the
`qdrant` extra, so a clean install without that extra raises
`EmbeddingMissingExtraError` rather than `ImportError`.

**Functions:**

- [**embed**](#agrag.embedding.FastEmbedBM25Embedder.embed) – Embed a batch of texts into BM25 sparse vectors.

**Attributes:**

- [**model**](#agrag.embedding.FastEmbedBM25Embedder.model) (<code>[str](#str)</code>) – The configured model name, or the FastEmbed default when unset.

**Parameters:**

- **model** (<code>[str](#str) | None</code>) – The FastEmbed BM25 model name. Defaults to FastEmbed's
  built-in BM25 model.

##### `agrag.embedding.FastEmbedBM25Embedder.embed`

```python
embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of texts into BM25 sparse vectors.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[SparseVector](#agrag.embedding.sparse_base.SparseVector)\]</code> – One sparse vector per input text, in the same order.

##### `agrag.embedding.FastEmbedBM25Embedder.model`

```python
model: str
```

The configured model name, or the FastEmbed default when unset.

#### `agrag.embedding.SentenceTransformerEmbedder`

```python
SentenceTransformerEmbedder(*, settings:EmbeddingSettings | None = None, cache:EmbeddingCache | None = None, model:object | None = None) -> None
```

Bases: <code>[Embedder](#agrag.embedding.base.Embedder)</code>

An embedder backed by sentence-transformers.

The model loads lazily on first `embed`, so constructing the embedder
does not touch the GPU or download weights. Every blocking call into the
model runs in a worker thread (`asyncio.to_thread`), so the event loop
stays free for other work while a large batch encodes.

**Functions:**

- [**embed**](#agrag.embedding.SentenceTransformerEmbedder.embed) – Embed a batch of texts, using the cache where possible.
- [**embed_one**](#agrag.embedding.SentenceTransformerEmbedder.embed_one) – Embed a single text.

**Attributes:**

- [**dimensions**](#agrag.embedding.SentenceTransformerEmbedder.dimensions) (<code>[int](#int)</code>) – The dimension the loaded model produces.
- [**model**](#agrag.embedding.SentenceTransformerEmbedder.model) (<code>[str](#str)</code>) – The configured model name.

**Parameters:**

- **settings** (<code>[EmbeddingSettings](#agrag.embedding.settings.EmbeddingSettings) | None</code>) – Embedder configuration. Defaults to `EmbeddingSettings()`.
- **cache** (<code>[EmbeddingCache](#agrag.embedding.base.EmbeddingCache) | None</code>) – An optional content-addressed cache. Defaults to a no-op cache.
- **model** (<code>[object](#object) | None</code>) – A pre-built sentence-transformers model, for tests. When set,
  `__init__` imports nothing and `embed` calls this object
  directly instead of building one.

##### `agrag.embedding.SentenceTransformerEmbedder.dimensions`

```python
dimensions: int
```

The dimension the loaded model produces.

Accessing this loads the model the first time.

**Raises:**

- <code>[EmbeddingMissingExtraError](#agrag.embedding.errors.EmbeddingMissingExtraError)</code> – sentence-transformers is not installed.

##### `agrag.embedding.SentenceTransformerEmbedder.embed`

```python
embed(texts:Sequence[str]) -> list[list[float]]
```

Embed a batch of texts, using the cache where possible.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[list](#list)\[[float](#float)\]\]</code> – One vector per input text, in the same order.

##### `agrag.embedding.SentenceTransformerEmbedder.embed_one`

```python
embed_one(text:str) -> list[float]
```

Embed a single text.

**Parameters:**

- **text** (<code>[str](#str)</code>) – The text to embed.

**Returns:**

- <code>[list](#list)\[[float](#float)\]</code> – The text's embedding vector.

##### `agrag.embedding.SentenceTransformerEmbedder.model`

```python
model: str
```

The configured model name.

#### `agrag.embedding.SparseEmbedder`

Bases: <code>[ABC](#abc.ABC)</code>

A component that turns text into sparse lexical vectors, for hybrid search.

**Functions:**

- [**embed**](#agrag.embedding.SparseEmbedder.embed) – Embed a batch of texts into sparse vectors.

**Attributes:**

- [**model**](#agrag.embedding.SparseEmbedder.model) (<code>[str](#str)</code>) –

##### `agrag.embedding.SparseEmbedder.embed`

```python
embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of texts into sparse vectors.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[SparseVector](#agrag.embedding.sparse_base.SparseVector)\]</code> – One sparse vector per input text, in the same order.

##### `agrag.embedding.SparseEmbedder.model`

```python
model: str
```

#### `agrag.embedding.SparseVector`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

A sparse vector: nonzero indices and their values.

**Attributes:**

- [**indices**](#agrag.embedding.SparseVector.indices) (<code>[list](#list)\[[int](#int)\]</code>) – The positions of nonzero entries.
- [**values**](#agrag.embedding.SparseVector.values) (<code>[list](#list)\[[float](#float)\]</code>) – The weight at each index, aligned with `indices`.

##### `agrag.embedding.SparseVector.indices`

```python
indices: list[int]
```

##### `agrag.embedding.SparseVector.values`

```python
values: list[float]
```

#### `agrag.embedding.base`

The Embedder and EmbeddingCache protocols.

**Classes:**

- [**Embedder**](#agrag.embedding.base.Embedder) – A component that turns text into dense embedding vectors.
- [**EmbeddingCache**](#agrag.embedding.base.EmbeddingCache) – A content-addressed cache for embedding vectors.
- [**NullEmbeddingCache**](#agrag.embedding.base.NullEmbeddingCache) – A cache that never stores anything. The default when none is injected.

##### `agrag.embedding.base.Embedder`

Bases: <code>[ABC](#abc.ABC)</code>

A component that turns text into dense embedding vectors.

**Functions:**

- [**embed**](#agrag.embedding.base.Embedder.embed) – Embed a batch of texts.
- [**embed_one**](#agrag.embedding.base.Embedder.embed_one) – Embed a single text.

**Attributes:**

- [**dimensions**](#agrag.embedding.base.Embedder.dimensions) (<code>[int](#int)</code>) –
- [**model**](#agrag.embedding.base.Embedder.model) (<code>[str](#str)</code>) –

###### `agrag.embedding.base.Embedder.dimensions`

```python
dimensions: int
```

###### `agrag.embedding.base.Embedder.embed`

```python
embed(texts:Sequence[str]) -> list[list[float]]
```

Embed a batch of texts.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[list](#list)\[[float](#float)\]\]</code> – One vector per input text, in the same order.

###### `agrag.embedding.base.Embedder.embed_one`

```python
embed_one(text:str) -> list[float]
```

Embed a single text.

**Parameters:**

- **text** (<code>[str](#str)</code>) – The text to embed.

**Returns:**

- <code>[list](#list)\[[float](#float)\]</code> – The text's embedding vector.

###### `agrag.embedding.base.Embedder.model`

```python
model: str
```

##### `agrag.embedding.base.EmbeddingCache`

Bases: <code>[ABC](#abc.ABC)</code>

A content-addressed cache for embedding vectors.

**Functions:**

- [**get**](#agrag.embedding.base.EmbeddingCache.get) – Return the cached vector for `(text, model)`, or `None` on a miss.
- [**set**](#agrag.embedding.base.EmbeddingCache.set) – Store `vector` under `(text, model)`.

###### `agrag.embedding.base.EmbeddingCache.get`

```python
get(*, text:str, model:str) -> list[float] | None
```

Return the cached vector for `(text, model)`, or `None` on a miss.

###### `agrag.embedding.base.EmbeddingCache.set`

```python
set(*, text:str, model:str, vector:list[float]) -> None
```

Store `vector` under `(text, model)`.

##### `agrag.embedding.base.NullEmbeddingCache`

Bases: <code>[EmbeddingCache](#agrag.embedding.base.EmbeddingCache)</code>

A cache that never stores anything. The default when none is injected.

**Functions:**

- [**get**](#agrag.embedding.base.NullEmbeddingCache.get) – Always miss.
- [**set**](#agrag.embedding.base.NullEmbeddingCache.set) – Do nothing.

###### `agrag.embedding.base.NullEmbeddingCache.get`

```python
get(*, text:str, model:str) -> list[float] | None
```

Always miss.

###### `agrag.embedding.base.NullEmbeddingCache.set`

```python
set(*, text:str, model:str, vector:list[float]) -> None
```

Do nothing.

#### `agrag.embedding.build_embedder`

```python
build_embedder(value:str | Embedder) -> Embedder
```

Build an embedder from a model name, or return an embedder unchanged.

**Parameters:**

- **value** (<code>[str](#str) | [Embedder](#agrag.embedding.base.Embedder)</code>) – A sentence-transformers model name, such as
  `"ibm-granite/granite-embedding-small-english-r2"` (the default
  model), or an already-constructed `Embedder` for full control
  over device, batching, or caching.

**Returns:**

- <code>[Embedder](#agrag.embedding.base.Embedder)</code> – A ready-to-use embedder.

#### `agrag.embedding.errors`

Errors that the embedding layer raises.

**Classes:**

- [**EmbeddingDimensionMismatchError**](#agrag.embedding.errors.EmbeddingDimensionMismatchError) – A stored collection or index expects a different embedding dimension.
- [**EmbeddingError**](#agrag.embedding.errors.EmbeddingError) – The base class for every embedding error.
- [**EmbeddingMissingExtraError**](#agrag.embedding.errors.EmbeddingMissingExtraError) – An embedder exists, but its package extra is not installed.

##### `agrag.embedding.errors.EmbeddingDimensionMismatchError`

```python
EmbeddingDimensionMismatchError(*, expected:int, actual:int) -> None
```

Bases: <code>[EmbeddingError](#agrag.embedding.errors.EmbeddingError)</code>

A stored collection or index expects a different embedding dimension.

**Attributes:**

- [**expected**](#agrag.embedding.errors.EmbeddingDimensionMismatchError.expected) – The dimension the collection or index was created with.
- [**actual**](#agrag.embedding.errors.EmbeddingDimensionMismatchError.actual) – The dimension the embedder actually produces.

###### `agrag.embedding.errors.EmbeddingDimensionMismatchError.actual`

```python
actual = actual
```

###### `agrag.embedding.errors.EmbeddingDimensionMismatchError.expected`

```python
expected = expected
```

##### `agrag.embedding.errors.EmbeddingError`

Bases: <code>[Exception](#Exception)</code>

The base class for every embedding error.

##### `agrag.embedding.errors.EmbeddingMissingExtraError`

```python
EmbeddingMissingExtraError(extra:str) -> None
```

Bases: <code>[EmbeddingError](#agrag.embedding.errors.EmbeddingError)</code>

An embedder exists, but its package extra is not installed.

**Attributes:**

- [**extra**](#agrag.embedding.errors.EmbeddingMissingExtraError.extra) – The name of the package extra to install.

###### `agrag.embedding.errors.EmbeddingMissingExtraError.extra`

```python
extra = extra
```

#### `agrag.embedding.fastembed_bm25`

BM25 sparse embedder backed by FastEmbed.

**Classes:**

- [**FastEmbedBM25Embedder**](#agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder) – A sparse BM25 embedder built on FastEmbed.

**Attributes:**

- [**DEFAULT_BM25_MODEL**](#agrag.embedding.fastembed_bm25.DEFAULT_BM25_MODEL) –

##### `agrag.embedding.fastembed_bm25.DEFAULT_BM25_MODEL`

```python
DEFAULT_BM25_MODEL = 'Qdrant/bm25'
```

##### `agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder`

```python
FastEmbedBM25Embedder(*, model:str | None = None) -> None
```

Bases: <code>[SparseEmbedder](#agrag.embedding.sparse_base.SparseEmbedder)</code>

A sparse BM25 embedder built on FastEmbed.

The model loads lazily on first `embed`, so constructing the embedder
does not download weights. Each blocking call into FastEmbed runs in a
worker thread, keeping the event loop free. FastEmbed ships with the
`qdrant` extra, so a clean install without that extra raises
`EmbeddingMissingExtraError` rather than `ImportError`.

**Functions:**

- [**embed**](#agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder.embed) – Embed a batch of texts into BM25 sparse vectors.

**Attributes:**

- [**model**](#agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder.model) (<code>[str](#str)</code>) – The configured model name, or the FastEmbed default when unset.

**Parameters:**

- **model** (<code>[str](#str) | None</code>) – The FastEmbed BM25 model name. Defaults to FastEmbed's
  built-in BM25 model.

###### `agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder.embed`

```python
embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of texts into BM25 sparse vectors.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[SparseVector](#agrag.embedding.sparse_base.SparseVector)\]</code> – One sparse vector per input text, in the same order.

###### `agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder.model`

```python
model: str
```

The configured model name, or the FastEmbed default when unset.

#### `agrag.embedding.sentence_transformers`

Sentence-transformers embedder implementation.

**Classes:**

- [**SentenceTransformerEmbedder**](#agrag.embedding.sentence_transformers.SentenceTransformerEmbedder) – An embedder backed by sentence-transformers.

##### `agrag.embedding.sentence_transformers.SentenceTransformerEmbedder`

```python
SentenceTransformerEmbedder(*, settings:EmbeddingSettings | None = None, cache:EmbeddingCache | None = None, model:object | None = None) -> None
```

Bases: <code>[Embedder](#agrag.embedding.base.Embedder)</code>

An embedder backed by sentence-transformers.

The model loads lazily on first `embed`, so constructing the embedder
does not touch the GPU or download weights. Every blocking call into the
model runs in a worker thread (`asyncio.to_thread`), so the event loop
stays free for other work while a large batch encodes.

**Functions:**

- [**embed**](#agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.embed) – Embed a batch of texts, using the cache where possible.
- [**embed_one**](#agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.embed_one) – Embed a single text.

**Attributes:**

- [**dimensions**](#agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.dimensions) (<code>[int](#int)</code>) – The dimension the loaded model produces.
- [**model**](#agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.model) (<code>[str](#str)</code>) – The configured model name.

**Parameters:**

- **settings** (<code>[EmbeddingSettings](#agrag.embedding.settings.EmbeddingSettings) | None</code>) – Embedder configuration. Defaults to `EmbeddingSettings()`.
- **cache** (<code>[EmbeddingCache](#agrag.embedding.base.EmbeddingCache) | None</code>) – An optional content-addressed cache. Defaults to a no-op cache.
- **model** (<code>[object](#object) | None</code>) – A pre-built sentence-transformers model, for tests. When set,
  `__init__` imports nothing and `embed` calls this object
  directly instead of building one.

###### `agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.dimensions`

```python
dimensions: int
```

The dimension the loaded model produces.

Accessing this loads the model the first time.

**Raises:**

- <code>[EmbeddingMissingExtraError](#agrag.embedding.errors.EmbeddingMissingExtraError)</code> – sentence-transformers is not installed.

###### `agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.embed`

```python
embed(texts:Sequence[str]) -> list[list[float]]
```

Embed a batch of texts, using the cache where possible.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[list](#list)\[[float](#float)\]\]</code> – One vector per input text, in the same order.

###### `agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.embed_one`

```python
embed_one(text:str) -> list[float]
```

Embed a single text.

**Parameters:**

- **text** (<code>[str](#str)</code>) – The text to embed.

**Returns:**

- <code>[list](#list)\[[float](#float)\]</code> – The text's embedding vector.

###### `agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.model`

```python
model: str
```

The configured model name.

#### `agrag.embedding.settings`

Settings for the sentence-transformers embedder.

**Classes:**

- [**EmbeddingSettings**](#agrag.embedding.settings.EmbeddingSettings) – Sentence-transformers embedder configuration.

##### `agrag.embedding.settings.EmbeddingSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Sentence-transformers embedder configuration.

All fields are overridable via environment variables with the
`EMBEDDING_` prefix.

**Attributes:**

- [**model**](#agrag.embedding.settings.EmbeddingSettings.model) (<code>[str](#str)</code>) – The sentence-transformers model name or path. Env: `EMBEDDING_MODEL`.
- [**device**](#agrag.embedding.settings.EmbeddingSettings.device) (<code>[str](#str) | None</code>) – The device to load the model on, such as `"cpu"` or `"cuda"`.
  `None` uses sentence-transformers' own default detection. Env:
  `EMBEDDING_DEVICE`.
- [**normalize**](#agrag.embedding.settings.EmbeddingSettings.normalize) (<code>[bool](#bool)</code>) – Whether to L2-normalize output vectors. Env: `EMBEDDING_NORMALIZE`.
- [**batch_size**](#agrag.embedding.settings.EmbeddingSettings.batch_size) (<code>[int](#int)</code>) – The number of texts encoded per `model.encode` call. Env:
  `EMBEDDING_BATCH_SIZE`.
- [**cache_folder**](#agrag.embedding.settings.EmbeddingSettings.cache_folder) (<code>[str](#str) | None</code>) – Where sentence-transformers caches downloaded models.
  `None` uses the library default. Env: `EMBEDDING_CACHE_FOLDER`.

###### `agrag.embedding.settings.EmbeddingSettings.batch_size`

```python
batch_size: int = 32
```

###### `agrag.embedding.settings.EmbeddingSettings.cache_folder`

```python
cache_folder: str | None = None
```

###### `agrag.embedding.settings.EmbeddingSettings.device`

```python
device: str | None = None
```

###### `agrag.embedding.settings.EmbeddingSettings.model`

```python
model: str = 'ibm-granite/granite-embedding-small-english-r2'
```

###### `agrag.embedding.settings.EmbeddingSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='EMBEDDING_', env_file='.env', extra='ignore')
```

###### `agrag.embedding.settings.EmbeddingSettings.normalize`

```python
normalize: bool = True
```

#### `agrag.embedding.sparse_base`

Sparse lexical vectors and the sparse embedder protocol.

**Classes:**

- [**SparseEmbedder**](#agrag.embedding.sparse_base.SparseEmbedder) – A component that turns text into sparse lexical vectors, for hybrid search.
- [**SparseVector**](#agrag.embedding.sparse_base.SparseVector) – A sparse vector: nonzero indices and their values.

##### `agrag.embedding.sparse_base.SparseEmbedder`

Bases: <code>[ABC](#abc.ABC)</code>

A component that turns text into sparse lexical vectors, for hybrid search.

**Functions:**

- [**embed**](#agrag.embedding.sparse_base.SparseEmbedder.embed) – Embed a batch of texts into sparse vectors.

**Attributes:**

- [**model**](#agrag.embedding.sparse_base.SparseEmbedder.model) (<code>[str](#str)</code>) –

###### `agrag.embedding.sparse_base.SparseEmbedder.embed`

```python
embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of texts into sparse vectors.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[SparseVector](#agrag.embedding.sparse_base.SparseVector)\]</code> – One sparse vector per input text, in the same order.

###### `agrag.embedding.sparse_base.SparseEmbedder.model`

```python
model: str
```

##### `agrag.embedding.sparse_base.SparseVector`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

A sparse vector: nonzero indices and their values.

**Attributes:**

- [**indices**](#agrag.embedding.sparse_base.SparseVector.indices) (<code>[list](#list)\[[int](#int)\]</code>) – The positions of nonzero entries.
- [**values**](#agrag.embedding.sparse_base.SparseVector.values) (<code>[list](#list)\[[float](#float)\]</code>) – The weight at each index, aligned with `indices`.

###### `agrag.embedding.sparse_base.SparseVector.indices`

```python
indices: list[int]
```

###### `agrag.embedding.sparse_base.SparseVector.values`

```python
values: list[float]
```

### `agrag.graphdb`

Graph storage backends and the build shortcut.

**Modules:**

- [**base**](#agrag.graphdb.base) – The GraphStore abstraction and its build shortcut helpers.
- [**errors**](#agrag.graphdb.errors) – Errors that the graph-store layer raises.
- [**neo4j**](#agrag.graphdb.neo4j) – Neo4j graph-store backend.
- [**serialize**](#agrag.graphdb.serialize) – Convert graph records into Neo4j-driver-friendly parameters.
- [**settings**](#agrag.graphdb.settings) – Settings for the Neo4j graph-store backend.

**Classes:**

- [**GraphStore**](#agrag.graphdb.GraphStore) – A graph database backend: schema, writes, and native vector search.
- [**GraphStoreError**](#agrag.graphdb.GraphStoreError) – The base class for every graph-store error.
- [**GraphStoreMissingExtraError**](#agrag.graphdb.GraphStoreMissingExtraError) – A graph store exists, but its package extra is not installed.
- [**Neo4jGraphStore**](#agrag.graphdb.Neo4jGraphStore) – A `GraphStore` backed by Neo4j, using native vector indexes.
- [**Neo4jSettings**](#agrag.graphdb.Neo4jSettings) – Neo4j connection configuration.

**Functions:**

- [**build_graph_store**](#agrag.graphdb.build_graph_store) – Build a graph store from a backend name, or return one unchanged.

**Attributes:**

- [**GraphStoreName**](#agrag.graphdb.GraphStoreName) –

#### `agrag.graphdb.GraphStore`

Bases: <code>[ABC](#abc.ABC)</code>

A graph database backend: schema, writes, and native vector search.

**Functions:**

- [**close**](#agrag.graphdb.GraphStore.close) – Release the backend connection.
- [**connect**](#agrag.graphdb.GraphStore.connect) – Open the backend connection and verify connectivity.
- [**ensure_vector_index**](#agrag.graphdb.GraphStore.ensure_vector_index) – Create a native vector index if it does not exist.
- [**execute_read**](#agrag.graphdb.GraphStore.execute_read) – Run a read transaction.
- [**execute_write**](#agrag.graphdb.GraphStore.execute_write) – Run a write transaction.
- [**session**](#agrag.graphdb.GraphStore.session) – Open a session as an async context manager.
- [**setup_constraints**](#agrag.graphdb.GraphStore.setup_constraints) – Create per-label uniqueness constraints for tracked labels.
- [**setup_indexes**](#agrag.graphdb.GraphStore.setup_indexes) – Create per-label property indexes for tracked labels.
- [**upsert_nodes**](#agrag.graphdb.GraphStore.upsert_nodes) – Write or merge nodes of one label.
- [**upsert_relations**](#agrag.graphdb.GraphStore.upsert_relations) – Write or merge relationships between existing nodes.
- [**vector_search**](#agrag.graphdb.GraphStore.vector_search) – Search nodes by dense vector.

##### `agrag.graphdb.GraphStore.close`

```python
close() -> None
```

Release the backend connection.

##### `agrag.graphdb.GraphStore.connect`

```python
connect() -> None
```

Open the backend connection and verify connectivity.

##### `agrag.graphdb.GraphStore.ensure_vector_index`

```python
ensure_vector_index(*, label:str, vector_property:str, dimensions:int, distance:Distance) -> None
```

Create a native vector index if it does not exist.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label to index.
- **vector_property** (<code>[str](#str)</code>) – The embedding property name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric.

##### `agrag.graphdb.GraphStore.execute_read`

```python
execute_read(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a read transaction.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The Cypher query to run.
- **parameters** (<code>[Mapping](#collections.abc.Mapping)\[[str](#str), [Any](#typing.Any)\] | None</code>) – The query parameters.

**Returns:**

- <code>[list](#list)\[[dict](#dict)\[[str](#str), [Any](#typing.Any)\]\]</code> – The result rows as dicts.

##### `agrag.graphdb.GraphStore.execute_write`

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write transaction.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The Cypher query to run.
- **parameters** (<code>[Mapping](#collections.abc.Mapping)\[[str](#str), [Any](#typing.Any)\] | None</code>) – The query parameters.

**Returns:**

- <code>[list](#list)\[[dict](#dict)\[[str](#str), [Any](#typing.Any)\]\]</code> – The result rows as dicts.

##### `agrag.graphdb.GraphStore.session`

```python
session() -> AbstractAsyncContextManager[Any]
```

Open a session as an async context manager.

**Returns:**

- <code>[AbstractAsyncContextManager](#contextlib.AbstractAsyncContextManager)\[[Any](#typing.Any)\]</code> – A context manager yielding a backend session.

##### `agrag.graphdb.GraphStore.setup_constraints`

```python
setup_constraints() -> None
```

Create per-label uniqueness constraints for tracked labels.

##### `agrag.graphdb.GraphStore.setup_indexes`

```python
setup_indexes() -> None
```

Create per-label property indexes for tracked labels.

##### `agrag.graphdb.GraphStore.upsert_nodes`

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256) -> None
```

Write or merge nodes of one label.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label.
- **nodes** (<code>[Sequence](#collections.abc.Sequence)\[[NodeRecord](#agrag.common.data_models.graph_record.NodeRecord)\]</code>) – The node records to upsert.
- **batch_size** (<code>[int](#int)</code>) – Records per backend write call.

##### `agrag.graphdb.GraphStore.upsert_relations`

```python
upsert_relations(relations:Sequence[RelationRecord], *, batch_size:int = 256) -> None
```

Write or merge relationships between existing nodes.

**Parameters:**

- **relations** (<code>[Sequence](#collections.abc.Sequence)\[[RelationRecord](#agrag.common.data_models.graph_record.RelationRecord)\]</code>) – The relation records to upsert.
- **batch_size** (<code>[int](#int)</code>) – Records per backend write call.

##### `agrag.graphdb.GraphStore.vector_search`

```python
vector_search(*, label:str, vector_property:str, query_vector:Sequence[float], limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search nodes by dense vector.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label to search.
- **vector_property** (<code>[str](#str)</code>) – The embedding property name.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – Maximum number of hits.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – An optional flat-dict filter on node properties.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

#### `agrag.graphdb.GraphStoreError`

Bases: <code>[Exception](#Exception)</code>

The base class for every graph-store error.

#### `agrag.graphdb.GraphStoreMissingExtraError`

```python
GraphStoreMissingExtraError(extra:str) -> None
```

Bases: <code>[GraphStoreError](#agrag.graphdb.errors.GraphStoreError)</code>

A graph store exists, but its package extra is not installed.

**Attributes:**

- [**extra**](#agrag.graphdb.GraphStoreMissingExtraError.extra) – The name of the package extra to install.

##### `agrag.graphdb.GraphStoreMissingExtraError.extra`

```python
extra = extra
```

#### `agrag.graphdb.GraphStoreName`

```python
GraphStoreName = Literal['neo4j']
```

#### `agrag.graphdb.Neo4jGraphStore`

```python
Neo4jGraphStore(*, settings:Neo4jSettings | None = None, driver:AsyncDriver | None = None) -> None
```

Bases: <code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>

A `GraphStore` backed by Neo4j, using native vector indexes.

The driver connects lazily on first use, so constructing the store does not
open a network connection. `execute_read`/`execute_write` wrap the
driver's managed transactions with no added retry loop, per ADR 0027.

**Functions:**

- [**close**](#agrag.graphdb.Neo4jGraphStore.close) – Close the driver, releasing its connection pool.
- [**connect**](#agrag.graphdb.Neo4jGraphStore.connect) – Open the driver and verify connectivity.
- [**ensure_vector_index**](#agrag.graphdb.Neo4jGraphStore.ensure_vector_index) – Create a native vector index if it does not exist.
- [**execute_read**](#agrag.graphdb.Neo4jGraphStore.execute_read) – Run a read transaction and return its rows.
- [**execute_write**](#agrag.graphdb.Neo4jGraphStore.execute_write) – Run a write transaction and return its rows.
- [**session**](#agrag.graphdb.Neo4jGraphStore.session) – Open a session to the configured database.
- [**setup_constraints**](#agrag.graphdb.Neo4jGraphStore.setup_constraints) – Create a uniqueness constraint on `id` for every tracked label.
- [**setup_indexes**](#agrag.graphdb.Neo4jGraphStore.setup_indexes) – Create a range index on `id` for every tracked label.
- [**upsert_nodes**](#agrag.graphdb.Neo4jGraphStore.upsert_nodes) – Write or merge nodes of one label.
- [**upsert_relations**](#agrag.graphdb.Neo4jGraphStore.upsert_relations) – Write or merge relationships between existing nodes.
- [**vector_search**](#agrag.graphdb.Neo4jGraphStore.vector_search) – Search nodes by dense vector using the native vector index.

**Parameters:**

- **settings** (<code>[Neo4jSettings](#agrag.graphdb.settings.Neo4jSettings) | None</code>) – Neo4j connection settings. Defaults to `Neo4jSettings()`.
- **driver** (<code>[AsyncDriver](#neo4j.AsyncDriver) | None</code>) – A pre-built `AsyncDriver`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.

##### `agrag.graphdb.Neo4jGraphStore.close`

```python
close() -> None
```

Close the driver, releasing its connection pool.

##### `agrag.graphdb.Neo4jGraphStore.connect`

```python
connect() -> None
```

Open the driver and verify connectivity.

##### `agrag.graphdb.Neo4jGraphStore.ensure_vector_index`

```python
ensure_vector_index(*, label:str, vector_property:str, dimensions:int, distance:Distance) -> None
```

Create a native vector index if it does not exist.

##### `agrag.graphdb.Neo4jGraphStore.execute_read`

```python
execute_read(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a read transaction and return its rows.

##### `agrag.graphdb.Neo4jGraphStore.execute_write`

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write transaction and return its rows.

##### `agrag.graphdb.Neo4jGraphStore.session`

```python
session() -> AbstractAsyncContextManager[Any]
```

Open a session to the configured database.

##### `agrag.graphdb.Neo4jGraphStore.setup_constraints`

```python
setup_constraints() -> None
```

Create a uniqueness constraint on `id` for every tracked label.

##### `agrag.graphdb.Neo4jGraphStore.setup_indexes`

```python
setup_indexes() -> None
```

Create a range index on `id` for every tracked label.

##### `agrag.graphdb.Neo4jGraphStore.upsert_nodes`

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256) -> None
```

Write or merge nodes of one label.

##### `agrag.graphdb.Neo4jGraphStore.upsert_relations`

```python
upsert_relations(relations:Sequence[RelationRecord], *, batch_size:int = 256) -> None
```

Write or merge relationships between existing nodes.

##### `agrag.graphdb.Neo4jGraphStore.vector_search`

```python
vector_search(*, label:str, vector_property:str, query_vector:Sequence[float], limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search nodes by dense vector using the native vector index.

#### `agrag.graphdb.Neo4jSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Neo4j connection configuration.

**Attributes:**

- [**uri**](#agrag.graphdb.Neo4jSettings.uri) (<code>[str](#str)</code>) – The Bolt connection URI, including scheme (`neo4j+s://` for
  Aura). Env: `NEO4J_URI`.
- [**username**](#agrag.graphdb.Neo4jSettings.username) (<code>[str](#str)</code>) – The database username. Env: `NEO4J_USERNAME`.
- [**password**](#agrag.graphdb.Neo4jSettings.password) (<code>[SecretStr](#pydantic.SecretStr)</code>) – The database password. Env: `NEO4J_PASSWORD`.
- [**database**](#agrag.graphdb.Neo4jSettings.database) (<code>[str](#str)</code>) – The target database name. Env: `NEO4J_DATABASE`.
- [**max_connection_lifetime**](#agrag.graphdb.Neo4jSettings.max_connection_lifetime) (<code>[int](#int)</code>) – The maximum seconds a pooled connection
  lives, kept well below Aura's roughly five-minute idle timeout.
  Env: `NEO4J_MAX_CONNECTION_LIFETIME`.

##### `agrag.graphdb.Neo4jSettings.database`

```python
database: str = 'neo4j'
```

##### `agrag.graphdb.Neo4jSettings.max_connection_lifetime`

```python
max_connection_lifetime: int = 240
```

##### `agrag.graphdb.Neo4jSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='NEO4J_', env_file='.env', extra='ignore')
```

##### `agrag.graphdb.Neo4jSettings.password`

```python
password: SecretStr = SecretStr('neo4j')
```

##### `agrag.graphdb.Neo4jSettings.uri`

```python
uri: str = 'bolt://localhost:7687'
```

##### `agrag.graphdb.Neo4jSettings.username`

```python
username: str = 'neo4j'
```

#### `agrag.graphdb.base`

The GraphStore abstraction and its build shortcut helpers.

**Classes:**

- [**GraphStore**](#agrag.graphdb.base.GraphStore) – A graph database backend: schema, writes, and native vector search.

##### `agrag.graphdb.base.GraphStore`

Bases: <code>[ABC](#abc.ABC)</code>

A graph database backend: schema, writes, and native vector search.

**Functions:**

- [**close**](#agrag.graphdb.base.GraphStore.close) – Release the backend connection.
- [**connect**](#agrag.graphdb.base.GraphStore.connect) – Open the backend connection and verify connectivity.
- [**ensure_vector_index**](#agrag.graphdb.base.GraphStore.ensure_vector_index) – Create a native vector index if it does not exist.
- [**execute_read**](#agrag.graphdb.base.GraphStore.execute_read) – Run a read transaction.
- [**execute_write**](#agrag.graphdb.base.GraphStore.execute_write) – Run a write transaction.
- [**session**](#agrag.graphdb.base.GraphStore.session) – Open a session as an async context manager.
- [**setup_constraints**](#agrag.graphdb.base.GraphStore.setup_constraints) – Create per-label uniqueness constraints for tracked labels.
- [**setup_indexes**](#agrag.graphdb.base.GraphStore.setup_indexes) – Create per-label property indexes for tracked labels.
- [**upsert_nodes**](#agrag.graphdb.base.GraphStore.upsert_nodes) – Write or merge nodes of one label.
- [**upsert_relations**](#agrag.graphdb.base.GraphStore.upsert_relations) – Write or merge relationships between existing nodes.
- [**vector_search**](#agrag.graphdb.base.GraphStore.vector_search) – Search nodes by dense vector.

###### `agrag.graphdb.base.GraphStore.close`

```python
close() -> None
```

Release the backend connection.

###### `agrag.graphdb.base.GraphStore.connect`

```python
connect() -> None
```

Open the backend connection and verify connectivity.

###### `agrag.graphdb.base.GraphStore.ensure_vector_index`

```python
ensure_vector_index(*, label:str, vector_property:str, dimensions:int, distance:Distance) -> None
```

Create a native vector index if it does not exist.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label to index.
- **vector_property** (<code>[str](#str)</code>) – The embedding property name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric.

###### `agrag.graphdb.base.GraphStore.execute_read`

```python
execute_read(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a read transaction.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The Cypher query to run.
- **parameters** (<code>[Mapping](#collections.abc.Mapping)\[[str](#str), [Any](#typing.Any)\] | None</code>) – The query parameters.

**Returns:**

- <code>[list](#list)\[[dict](#dict)\[[str](#str), [Any](#typing.Any)\]\]</code> – The result rows as dicts.

###### `agrag.graphdb.base.GraphStore.execute_write`

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write transaction.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The Cypher query to run.
- **parameters** (<code>[Mapping](#collections.abc.Mapping)\[[str](#str), [Any](#typing.Any)\] | None</code>) – The query parameters.

**Returns:**

- <code>[list](#list)\[[dict](#dict)\[[str](#str), [Any](#typing.Any)\]\]</code> – The result rows as dicts.

###### `agrag.graphdb.base.GraphStore.session`

```python
session() -> AbstractAsyncContextManager[Any]
```

Open a session as an async context manager.

**Returns:**

- <code>[AbstractAsyncContextManager](#contextlib.AbstractAsyncContextManager)\[[Any](#typing.Any)\]</code> – A context manager yielding a backend session.

###### `agrag.graphdb.base.GraphStore.setup_constraints`

```python
setup_constraints() -> None
```

Create per-label uniqueness constraints for tracked labels.

###### `agrag.graphdb.base.GraphStore.setup_indexes`

```python
setup_indexes() -> None
```

Create per-label property indexes for tracked labels.

###### `agrag.graphdb.base.GraphStore.upsert_nodes`

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256) -> None
```

Write or merge nodes of one label.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label.
- **nodes** (<code>[Sequence](#collections.abc.Sequence)\[[NodeRecord](#agrag.common.data_models.graph_record.NodeRecord)\]</code>) – The node records to upsert.
- **batch_size** (<code>[int](#int)</code>) – Records per backend write call.

###### `agrag.graphdb.base.GraphStore.upsert_relations`

```python
upsert_relations(relations:Sequence[RelationRecord], *, batch_size:int = 256) -> None
```

Write or merge relationships between existing nodes.

**Parameters:**

- **relations** (<code>[Sequence](#collections.abc.Sequence)\[[RelationRecord](#agrag.common.data_models.graph_record.RelationRecord)\]</code>) – The relation records to upsert.
- **batch_size** (<code>[int](#int)</code>) – Records per backend write call.

###### `agrag.graphdb.base.GraphStore.vector_search`

```python
vector_search(*, label:str, vector_property:str, query_vector:Sequence[float], limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search nodes by dense vector.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label to search.
- **vector_property** (<code>[str](#str)</code>) – The embedding property name.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – Maximum number of hits.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – An optional flat-dict filter on node properties.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

#### `agrag.graphdb.build_graph_store`

```python
build_graph_store(value:GraphStoreName | GraphStore) -> GraphStore
```

Build a graph store from a backend name, or return one unchanged.

**Parameters:**

- **value** (<code>[GraphStoreName](#agrag.graphdb.GraphStoreName) | [GraphStore](#agrag.graphdb.base.GraphStore)</code>) – `"neo4j"`, or an already-constructed `GraphStore`.

**Returns:**

- <code>[GraphStore](#agrag.graphdb.base.GraphStore)</code> – A ready-to-use graph store.

#### `agrag.graphdb.errors`

Errors that the graph-store layer raises.

**Classes:**

- [**GraphStoreError**](#agrag.graphdb.errors.GraphStoreError) – The base class for every graph-store error.
- [**GraphStoreMissingExtraError**](#agrag.graphdb.errors.GraphStoreMissingExtraError) – A graph store exists, but its package extra is not installed.

##### `agrag.graphdb.errors.GraphStoreError`

Bases: <code>[Exception](#Exception)</code>

The base class for every graph-store error.

##### `agrag.graphdb.errors.GraphStoreMissingExtraError`

```python
GraphStoreMissingExtraError(extra:str) -> None
```

Bases: <code>[GraphStoreError](#agrag.graphdb.errors.GraphStoreError)</code>

A graph store exists, but its package extra is not installed.

**Attributes:**

- [**extra**](#agrag.graphdb.errors.GraphStoreMissingExtraError.extra) – The name of the package extra to install.

###### `agrag.graphdb.errors.GraphStoreMissingExtraError.extra`

```python
extra = extra
```

#### `agrag.graphdb.neo4j`

Neo4j graph-store backend.

**Classes:**

- [**Neo4jGraphStore**](#agrag.graphdb.neo4j.Neo4jGraphStore) – A `GraphStore` backed by Neo4j, using native vector indexes.

##### `agrag.graphdb.neo4j.Neo4jGraphStore`

```python
Neo4jGraphStore(*, settings:Neo4jSettings | None = None, driver:AsyncDriver | None = None) -> None
```

Bases: <code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>

A `GraphStore` backed by Neo4j, using native vector indexes.

The driver connects lazily on first use, so constructing the store does not
open a network connection. `execute_read`/`execute_write` wrap the
driver's managed transactions with no added retry loop, per ADR 0027.

**Functions:**

- [**close**](#agrag.graphdb.neo4j.Neo4jGraphStore.close) – Close the driver, releasing its connection pool.
- [**connect**](#agrag.graphdb.neo4j.Neo4jGraphStore.connect) – Open the driver and verify connectivity.
- [**ensure_vector_index**](#agrag.graphdb.neo4j.Neo4jGraphStore.ensure_vector_index) – Create a native vector index if it does not exist.
- [**execute_read**](#agrag.graphdb.neo4j.Neo4jGraphStore.execute_read) – Run a read transaction and return its rows.
- [**execute_write**](#agrag.graphdb.neo4j.Neo4jGraphStore.execute_write) – Run a write transaction and return its rows.
- [**session**](#agrag.graphdb.neo4j.Neo4jGraphStore.session) – Open a session to the configured database.
- [**setup_constraints**](#agrag.graphdb.neo4j.Neo4jGraphStore.setup_constraints) – Create a uniqueness constraint on `id` for every tracked label.
- [**setup_indexes**](#agrag.graphdb.neo4j.Neo4jGraphStore.setup_indexes) – Create a range index on `id` for every tracked label.
- [**upsert_nodes**](#agrag.graphdb.neo4j.Neo4jGraphStore.upsert_nodes) – Write or merge nodes of one label.
- [**upsert_relations**](#agrag.graphdb.neo4j.Neo4jGraphStore.upsert_relations) – Write or merge relationships between existing nodes.
- [**vector_search**](#agrag.graphdb.neo4j.Neo4jGraphStore.vector_search) – Search nodes by dense vector using the native vector index.

**Parameters:**

- **settings** (<code>[Neo4jSettings](#agrag.graphdb.settings.Neo4jSettings) | None</code>) – Neo4j connection settings. Defaults to `Neo4jSettings()`.
- **driver** (<code>[AsyncDriver](#neo4j.AsyncDriver) | None</code>) – A pre-built `AsyncDriver`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.close`

```python
close() -> None
```

Close the driver, releasing its connection pool.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.connect`

```python
connect() -> None
```

Open the driver and verify connectivity.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.ensure_vector_index`

```python
ensure_vector_index(*, label:str, vector_property:str, dimensions:int, distance:Distance) -> None
```

Create a native vector index if it does not exist.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.execute_read`

```python
execute_read(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a read transaction and return its rows.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.execute_write`

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write transaction and return its rows.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.session`

```python
session() -> AbstractAsyncContextManager[Any]
```

Open a session to the configured database.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.setup_constraints`

```python
setup_constraints() -> None
```

Create a uniqueness constraint on `id` for every tracked label.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.setup_indexes`

```python
setup_indexes() -> None
```

Create a range index on `id` for every tracked label.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.upsert_nodes`

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256) -> None
```

Write or merge nodes of one label.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.upsert_relations`

```python
upsert_relations(relations:Sequence[RelationRecord], *, batch_size:int = 256) -> None
```

Write or merge relationships between existing nodes.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.vector_search`

```python
vector_search(*, label:str, vector_property:str, query_vector:Sequence[float], limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search nodes by dense vector using the native vector index.

#### `agrag.graphdb.serialize`

Convert graph records into Neo4j-driver-friendly parameters.

**Functions:**

- [**node_params**](#agrag.graphdb.serialize.node_params) – Build the `$records` entry for a node upsert.
- [**relation_params**](#agrag.graphdb.serialize.relation_params) – Build the `$records` entry for a relationship upsert.

##### `agrag.graphdb.serialize.node_params`

```python
node_params(record:NodeRecord) -> dict[str, Any]
```

Build the `$records` entry for a node upsert.

**Parameters:**

- **record** (<code>[NodeRecord](#agrag.common.data_models.graph_record.NodeRecord)</code>) – The node record to serialize.

**Returns:**

- <code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code> – A dict with `id` (string) and `properties` (converted).

##### `agrag.graphdb.serialize.relation_params`

```python
relation_params(record:RelationRecord) -> dict[str, Any]
```

Build the `$records` entry for a relationship upsert.

**Parameters:**

- **record** (<code>[RelationRecord](#agrag.common.data_models.graph_record.RelationRecord)</code>) – The relation record to serialize.

**Returns:**

- <code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code> – A dict with `id`, `start_id`, `end_id`, and `properties`.

#### `agrag.graphdb.settings`

Settings for the Neo4j graph-store backend.

**Classes:**

- [**Neo4jSettings**](#agrag.graphdb.settings.Neo4jSettings) – Neo4j connection configuration.

##### `agrag.graphdb.settings.Neo4jSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Neo4j connection configuration.

**Attributes:**

- [**uri**](#agrag.graphdb.settings.Neo4jSettings.uri) (<code>[str](#str)</code>) – The Bolt connection URI, including scheme (`neo4j+s://` for
  Aura). Env: `NEO4J_URI`.
- [**username**](#agrag.graphdb.settings.Neo4jSettings.username) (<code>[str](#str)</code>) – The database username. Env: `NEO4J_USERNAME`.
- [**password**](#agrag.graphdb.settings.Neo4jSettings.password) (<code>[SecretStr](#pydantic.SecretStr)</code>) – The database password. Env: `NEO4J_PASSWORD`.
- [**database**](#agrag.graphdb.settings.Neo4jSettings.database) (<code>[str](#str)</code>) – The target database name. Env: `NEO4J_DATABASE`.
- [**max_connection_lifetime**](#agrag.graphdb.settings.Neo4jSettings.max_connection_lifetime) (<code>[int](#int)</code>) – The maximum seconds a pooled connection
  lives, kept well below Aura's roughly five-minute idle timeout.
  Env: `NEO4J_MAX_CONNECTION_LIFETIME`.

###### `agrag.graphdb.settings.Neo4jSettings.database`

```python
database: str = 'neo4j'
```

###### `agrag.graphdb.settings.Neo4jSettings.max_connection_lifetime`

```python
max_connection_lifetime: int = 240
```

###### `agrag.graphdb.settings.Neo4jSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='NEO4J_', env_file='.env', extra='ignore')
```

###### `agrag.graphdb.settings.Neo4jSettings.password`

```python
password: SecretStr = SecretStr('neo4j')
```

###### `agrag.graphdb.settings.Neo4jSettings.uri`

```python
uri: str = 'bolt://localhost:7687'
```

###### `agrag.graphdb.settings.Neo4jSettings.username`

```python
username: str = 'neo4j'
```

### `agrag.ingestion`

The ingestion package.

**Modules:**

- [**graph**](#agrag.ingestion.graph) – The public Graph API for ingestion.

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

### `agrag.vectordb`

Vector storage backends and the build shortcut.

**Modules:**

- [**base**](#agrag.vectordb.base) – The VectorStore abstraction and its build shortcut.
- [**errors**](#agrag.vectordb.errors) – Errors that the vector-store layer raises.
- [**milvus**](#agrag.vectordb.milvus) – Milvus vector-store backend.
- [**qdrant**](#agrag.vectordb.qdrant) – Qdrant vector-store backend.
- [**settings**](#agrag.vectordb.settings) – Settings for vector-store backends.
- [**weaviate**](#agrag.vectordb.weaviate) – Weaviate vector-store backend.

**Classes:**

- [**CollectionDimensionMismatchError**](#agrag.vectordb.CollectionDimensionMismatchError) – A collection already exists with a different embedding dimension.
- [**MilvusSettings**](#agrag.vectordb.MilvusSettings) – Milvus connection configuration.
- [**MilvusVectorStore**](#agrag.vectordb.MilvusVectorStore) – A `VectorStore` backed by Milvus, including native hybrid search.
- [**QdrantSettings**](#agrag.vectordb.QdrantSettings) – Qdrant connection configuration.
- [**QdrantVectorStore**](#agrag.vectordb.QdrantVectorStore) – A `VectorStore` backed by Qdrant, including native hybrid search.
- [**VectorStore**](#agrag.vectordb.VectorStore) – A vector database backend: collection lifecycle, writes, and search.
- [**VectorStoreError**](#agrag.vectordb.VectorStoreError) – The base class for every vector-store error.
- [**VectorStoreMissingExtraError**](#agrag.vectordb.VectorStoreMissingExtraError) – A vector store exists, but its package extra is not installed.
- [**WeaviateSettings**](#agrag.vectordb.WeaviateSettings) – Weaviate connection configuration.
- [**WeaviateVectorStore**](#agrag.vectordb.WeaviateVectorStore) – A `VectorStore` backed by Weaviate, including native hybrid search.

**Functions:**

- [**build_vector_store**](#agrag.vectordb.build_vector_store) – Build a vector store from a backend name, or return one unchanged.

#### `agrag.vectordb.CollectionDimensionMismatchError`

```python
CollectionDimensionMismatchError(*, expected:int, actual:int) -> None
```

Bases: <code>[VectorStoreError](#agrag.vectordb.errors.VectorStoreError)</code>

A collection already exists with a different embedding dimension.

**Attributes:**

- [**expected**](#agrag.vectordb.CollectionDimensionMismatchError.expected) – The dimension the collection was created with.
- [**actual**](#agrag.vectordb.CollectionDimensionMismatchError.actual) – The dimension the caller requested.

##### `agrag.vectordb.CollectionDimensionMismatchError.actual`

```python
actual = actual
```

##### `agrag.vectordb.CollectionDimensionMismatchError.expected`

```python
expected = expected
```

#### `agrag.vectordb.MilvusSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Milvus connection configuration.

**Attributes:**

- [**uri**](#agrag.vectordb.MilvusSettings.uri) (<code>[str](#str)</code>) – The Milvus endpoint URI. Env: `MILVUS_URI`.
- [**token**](#agrag.vectordb.MilvusSettings.token) (<code>[str](#str)</code>) – The Milvus auth token. Empty string for an unauthenticated
  instance. Env: `MILVUS_TOKEN`.

##### `agrag.vectordb.MilvusSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='MILVUS_', env_file='.env', extra='ignore')
```

##### `agrag.vectordb.MilvusSettings.token`

```python
token: str = ''
```

##### `agrag.vectordb.MilvusSettings.uri`

```python
uri: str = 'http://localhost:19530'
```

#### `agrag.vectordb.MilvusVectorStore`

```python
MilvusVectorStore(*, settings:MilvusSettings | None = None, client:Any | None = None) -> None
```

Bases: <code>[VectorStore](#agrag.vectordb.base.VectorStore)</code>

A `VectorStore` backed by Milvus, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Milvus performs BM25 server-side, so hybrid
search needs no client-side sparse embedder; the sparse vector is computed
by a Milvus `Function` from the `text` field on write and at query time.

**Functions:**

- [**close**](#agrag.vectordb.MilvusVectorStore.close) – Release the backend connection.
- [**collection_exists**](#agrag.vectordb.MilvusVectorStore.collection_exists) – Report whether a collection exists.
- [**count**](#agrag.vectordb.MilvusVectorStore.count) – Count records in a collection.
- [**delete**](#agrag.vectordb.MilvusVectorStore.delete) – Delete records by id.
- [**delete_collection**](#agrag.vectordb.MilvusVectorStore.delete_collection) – Delete a collection and all its entities.
- [**ensure_collection**](#agrag.vectordb.MilvusVectorStore.ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag.vectordb.MilvusVectorStore.hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag.vectordb.MilvusVectorStore.initialize) – Check connectivity and authentication.
- [**retrieve**](#agrag.vectordb.MilvusVectorStore.retrieve) – Fetch records by id.
- [**scroll**](#agrag.vectordb.MilvusVectorStore.scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag.vectordb.MilvusVectorStore.search) – Search by dense vector only.
- [**upsert**](#agrag.vectordb.MilvusVectorStore.upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[MilvusSettings](#agrag.vectordb.settings.MilvusSettings) | None</code>) – Milvus connection settings. Defaults to
  `MilvusSettings()`.
- **client** (<code>[Any](#typing.Any) | None</code>) – A pre-built `AsyncMilvusClient`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.

##### `agrag.vectordb.MilvusVectorStore.close`

```python
close() -> None
```

Release the backend connection.

##### `agrag.vectordb.MilvusVectorStore.collection_exists`

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

**Returns:**

- <code>[bool](#bool)</code> – `True` if the collection exists.

##### `agrag.vectordb.MilvusVectorStore.count`

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to count.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on scalar fields.

**Returns:**

- <code>[int](#int)</code> – The number of matching records.

##### `agrag.vectordb.MilvusVectorStore.delete`

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to delete from.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to delete.

##### `agrag.vectordb.MilvusVectorStore.delete_collection`

```python
delete_collection(name:str) -> None
```

Delete a collection and all its entities.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

##### `agrag.vectordb.MilvusVectorStore.ensure_collection`

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

Milvus performs BM25 server-side, so the sparse field and its `Function`
are always provisioned; the `hybrid` flag is accepted for interface
parity but is a no-op here.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>[bool](#bool)</code>) – Accepted for interface parity; ignored by Milvus.

##### `agrag.vectordb.MilvusVectorStore.hybrid_search`

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

Fusion uses Milvus's native weighted reranker, which normalizes each
request's scores before applying `alpha`.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **query_text** (<code>[str](#str)</code>) – The query text, matched by BM25.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on scalar fields.
- **alpha** (<code>[float](#float)</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The fused hits, highest score first.

##### `agrag.vectordb.MilvusVectorStore.initialize`

```python
initialize() -> None
```

Check connectivity and authentication.

##### `agrag.vectordb.MilvusVectorStore.retrieve`

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to fetch.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – ids.

##### `agrag.vectordb.MilvusVectorStore.scroll`

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **limit** (<code>[int](#int)</code>) – The maximum number of records per page.
- **page_offset** (<code>[str](#str) | None</code>) – The numeric offset from a previous `scroll` call.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on scalar fields.
- **with_vectors** (<code>[bool](#bool)</code>) – Whether to return each record's vector.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The page of records and the next page offset, or `None` at the
- <code>[str](#str) | None</code> – end.

##### `agrag.vectordb.MilvusVectorStore.search`

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on scalar fields.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

##### `agrag.vectordb.MilvusVectorStore.upsert`

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Write or overwrite records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to write to.
- **records** (<code>[Sequence](#collections.abc.Sequence)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>[int](#int)</code>) – The number of records per backend write call.

#### `agrag.vectordb.QdrantSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Qdrant connection configuration.

**Attributes:**

- [**url**](#agrag.vectordb.QdrantSettings.url) (<code>[str](#str)</code>) – The Qdrant endpoint URL. Env: `QDRANT_URL`.
- [**api_key**](#agrag.vectordb.QdrantSettings.api_key) (<code>[str](#str)</code>) – The Qdrant API key. Env: `QDRANT_API_KEY`.

##### `agrag.vectordb.QdrantSettings.api_key`

```python
api_key: str = ''
```

##### `agrag.vectordb.QdrantSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='QDRANT_', env_file='.env', extra='ignore')
```

##### `agrag.vectordb.QdrantSettings.url`

```python
url: str = 'http://localhost:6333'
```

#### `agrag.vectordb.QdrantVectorStore`

```python
QdrantVectorStore(*, settings:QdrantSettings | None = None, sparse_embedder:SparseEmbedder | None = None, client:Any | None = None) -> None
```

Bases: <code>[VectorStore](#agrag.vectordb.base.VectorStore)</code>

A `VectorStore` backed by Qdrant, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Hybrid search builds its sparse query with a
`SparseEmbedder` that defaults to FastEmbed BM25 and loads only when a
hybrid call first runs, not at construction.

**Functions:**

- [**close**](#agrag.vectordb.QdrantVectorStore.close) – Release the backend connection.
- [**collection_exists**](#agrag.vectordb.QdrantVectorStore.collection_exists) – Report whether a collection exists.
- [**count**](#agrag.vectordb.QdrantVectorStore.count) – Count records in a collection.
- [**delete**](#agrag.vectordb.QdrantVectorStore.delete) – Delete records by id.
- [**delete_collection**](#agrag.vectordb.QdrantVectorStore.delete_collection) – Delete a collection and all its points.
- [**ensure_collection**](#agrag.vectordb.QdrantVectorStore.ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag.vectordb.QdrantVectorStore.hybrid_search) – Search by dense vector and keyword text, fused by a weighted blend.
- [**initialize**](#agrag.vectordb.QdrantVectorStore.initialize) – Check connectivity and authentication.
- [**retrieve**](#agrag.vectordb.QdrantVectorStore.retrieve) – Fetch records by id.
- [**scroll**](#agrag.vectordb.QdrantVectorStore.scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag.vectordb.QdrantVectorStore.search) – Search by dense vector only.
- [**upsert**](#agrag.vectordb.QdrantVectorStore.upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[QdrantSettings](#agrag.vectordb.settings.QdrantSettings) | None</code>) – Qdrant connection settings. Defaults to
  `QdrantSettings()`.
- **sparse_embedder** (<code>[SparseEmbedder](#agrag.embedding.sparse_base.SparseEmbedder) | None</code>) – The sparse embedder hybrid search uses. Defaults to
  a lazily-built `FastEmbedBM25Embedder`.
- **client** (<code>[Any](#typing.Any) | None</code>) – A pre-built `AsyncQdrantClient`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.

##### `agrag.vectordb.QdrantVectorStore.close`

```python
close() -> None
```

Release the backend connection.

##### `agrag.vectordb.QdrantVectorStore.collection_exists`

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

**Returns:**

- <code>[bool](#bool)</code> – `True` if the collection exists.

##### `agrag.vectordb.QdrantVectorStore.count`

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to count.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>[int](#int)</code> – The number of matching records.

##### `agrag.vectordb.QdrantVectorStore.delete`

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to delete from.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to delete.

##### `agrag.vectordb.QdrantVectorStore.delete_collection`

```python
delete_collection(name:str) -> None
```

Delete a collection and all its points.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

##### `agrag.vectordb.QdrantVectorStore.ensure_collection`

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>[bool](#bool)</code>) – Whether to provision the named sparse vector hybrid search
  needs.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag.vectordb.errors.CollectionDimensionMismatchError)</code> – The collection exists with a
  different dimension than `dimensions`.

##### `agrag.vectordb.QdrantVectorStore.hybrid_search`

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text, fused by a weighted blend.

Qdrant's native fusion methods (RRF, DBSF) have no continuous
dense/keyword weight, so this runs the dense and sparse (BM25)
searches independently, min-max normalizes each result set's scores
to `[0, 1]`, then combines them per id as
`alpha * dense + (1 - alpha) * sparse`. Each side fetches a wider
candidate pool than `limit` so a document strong on only one signal
still has a chance to reach the blended top results.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **query_text** (<code>[str](#str)</code>) – The query text, matched by BM25.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.
- **alpha** (<code>[float](#float)</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The blended hits, highest combined score first.

##### `agrag.vectordb.QdrantVectorStore.initialize`

```python
initialize() -> None
```

Check connectivity and authentication.

##### `agrag.vectordb.QdrantVectorStore.retrieve`

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to fetch.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – ids.

##### `agrag.vectordb.QdrantVectorStore.scroll`

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **limit** (<code>[int](#int)</code>) – The maximum number of records per page.
- **page_offset** (<code>[str](#str) | None</code>) – The offset from a previous `scroll` call.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.
- **with_vectors** (<code>[bool](#bool)</code>) – Whether to return each record's vector.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The page of records and the next page offset, or `None` at the
- <code>[str](#str) | None</code> – end.

##### `agrag.vectordb.QdrantVectorStore.search`

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

##### `agrag.vectordb.QdrantVectorStore.upsert`

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Write or overwrite records in a collection.

When `collection` was created with `ensure_collection(..., hybrid=True)`, each record's `payload["text"]` is also
sparse-embedded and stored under the named sparse vector, so
`hybrid_search`'s keyword arm has real vectors to match. A record
with no `text` payload key gets an empty sparse vector and only
ever surfaces through the dense side of a hybrid search.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to write to.
- **records** (<code>[Sequence](#collections.abc.Sequence)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>[int](#int)</code>) – The number of records per backend write call.

#### `agrag.vectordb.VectorStore`

Bases: <code>[ABC](#abc.ABC)</code>

A vector database backend: collection lifecycle, writes, and search.

**Functions:**

- [**close**](#agrag.vectordb.VectorStore.close) – Release the backend connection.
- [**collection_exists**](#agrag.vectordb.VectorStore.collection_exists) – Report whether a collection exists.
- [**count**](#agrag.vectordb.VectorStore.count) – Count records in a collection.
- [**delete**](#agrag.vectordb.VectorStore.delete) – Delete records by id.
- [**delete_collection**](#agrag.vectordb.VectorStore.delete_collection) – Delete a collection and all its points.
- [**ensure_collection**](#agrag.vectordb.VectorStore.ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag.vectordb.VectorStore.hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag.vectordb.VectorStore.initialize) – Check connectivity and authentication.
- [**retrieve**](#agrag.vectordb.VectorStore.retrieve) – Fetch records by id.
- [**scroll**](#agrag.vectordb.VectorStore.scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag.vectordb.VectorStore.search) – Search by dense vector only.
- [**upsert**](#agrag.vectordb.VectorStore.upsert) – Write or overwrite records in a collection.

##### `agrag.vectordb.VectorStore.close`

```python
close() -> None
```

Release the backend connection.

##### `agrag.vectordb.VectorStore.collection_exists`

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

**Returns:**

- <code>[bool](#bool)</code> – `True` if the collection exists.

##### `agrag.vectordb.VectorStore.count`

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to count.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.

**Returns:**

- <code>[int](#int)</code> – The number of matching records.

##### `agrag.vectordb.VectorStore.delete`

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to delete from.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to delete.

##### `agrag.vectordb.VectorStore.delete_collection`

```python
delete_collection(name:str) -> None
```

Delete a collection and all its points.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

##### `agrag.vectordb.VectorStore.ensure_collection`

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension. If the collection already
  exists with a different dimension, this raises.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>[bool](#bool)</code>) – Whether to additionally provision the sparse-vector
  configuration hybrid search needs. Ignored by backends that
  need no such provisioning.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag.vectordb.errors.CollectionDimensionMismatchError)</code> – The collection exists with a
  different dimension than `dimensions`.

##### `agrag.vectordb.VectorStore.hybrid_search`

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search. Must have been created with
  `ensure_collection(..., hybrid=True)`.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **query_text** (<code>[str](#str)</code>) – The query text, matched by keyword/BM25.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
- **alpha** (<code>[float](#float)</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword. Weaviate and Milvus apply this weight natively.
  Qdrant's native fusion (Reciprocal Rank Fusion) has no
  continuous weight, so it applies `alpha` by blending two
  independently-scored, min-max normalized result sets instead
  of a single native fused call.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The fused hits, highest score first.

##### `agrag.vectordb.VectorStore.initialize`

```python
initialize() -> None
```

Check connectivity and authentication.

**Raises:**

- <code>[VectorStoreError](#agrag.vectordb.errors.VectorStoreError)</code> – The backend is unreachable, or the credentials
  are rejected.

##### `agrag.vectordb.VectorStore.retrieve`

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to fetch.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – ids.

##### `agrag.vectordb.VectorStore.scroll`

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **limit** (<code>[int](#int)</code>) – The maximum number of records per page.
- **page_offset** (<code>[str](#str) | None</code>) – The offset from a previous `scroll` call, or
  `None` to start at the beginning.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
- **with_vectors** (<code>[bool](#bool)</code>) – Whether to return each record's vector.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The page of records and the next page offset, or `None` at the
- <code>[str](#str) | None</code> – end.

##### `agrag.vectordb.VectorStore.search`

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

##### `agrag.vectordb.VectorStore.upsert`

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Write or overwrite records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to write to.
- **records** (<code>[Sequence](#collections.abc.Sequence)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>[int](#int)</code>) – The number of records per backend write call.

#### `agrag.vectordb.VectorStoreError`

Bases: <code>[Exception](#Exception)</code>

The base class for every vector-store error.

#### `agrag.vectordb.VectorStoreMissingExtraError`

```python
VectorStoreMissingExtraError(extra:str) -> None
```

Bases: <code>[VectorStoreError](#agrag.vectordb.errors.VectorStoreError)</code>

A vector store exists, but its package extra is not installed.

**Attributes:**

- [**extra**](#agrag.vectordb.VectorStoreMissingExtraError.extra) – The name of the package extra to install.

##### `agrag.vectordb.VectorStoreMissingExtraError.extra`

```python
extra = extra
```

#### `agrag.vectordb.WeaviateSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Weaviate connection configuration.

**Attributes:**

- [**mode**](#agrag.vectordb.WeaviateSettings.mode) (<code>[Literal](#typing.Literal)['cloud', 'custom']</code>) – `"cloud"` connects to Weaviate Cloud. `"custom"` connects to
  a self-hosted instance (used by integration tests against the local
  Docker Compose instance) — an explicit field, not inferred from the
  URL, since inference caused real connection bugs in surveyed
  reference implementations. Env: `WEAVIATE_MODE`.
- [**url**](#agrag.vectordb.WeaviateSettings.url) (<code>[str](#str)</code>) – The Weaviate endpoint URL. For `"cloud"`, the cluster URL. For
  `"custom"`, the full host URL. Env: `WEAVIATE_URL`.
- [**api_key**](#agrag.vectordb.WeaviateSettings.api_key) (<code>[str](#str)</code>) – The Weaviate API key. Env: `WEAVIATE_API_KEY`.
- [**grpc_port**](#agrag.vectordb.WeaviateSettings.grpc_port) (<code>[int](#int)</code>) – The gRPC port, used by `"custom"` mode only (`"cloud"`
  mode infers it). Env: `WEAVIATE_GRPC_PORT`.

##### `agrag.vectordb.WeaviateSettings.api_key`

```python
api_key: str = ''
```

##### `agrag.vectordb.WeaviateSettings.grpc_port`

```python
grpc_port: int = 50051
```

##### `agrag.vectordb.WeaviateSettings.mode`

```python
mode: Literal['cloud', 'custom'] = 'cloud'
```

##### `agrag.vectordb.WeaviateSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='WEAVIATE_', env_file='.env', extra='ignore')
```

##### `agrag.vectordb.WeaviateSettings.url`

```python
url: str = 'http://localhost:8080'
```

#### `agrag.vectordb.WeaviateVectorStore`

```python
WeaviateVectorStore(*, settings:WeaviateSettings | None = None, client:Any | None = None) -> None
```

Bases: <code>[VectorStore](#agrag.vectordb.base.VectorStore)</code>

A `VectorStore` backed by Weaviate, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Weaviate does its own server-side BM25, so
hybrid search needs no client-side sparse embedder.

**Functions:**

- [**close**](#agrag.vectordb.WeaviateVectorStore.close) – Release the backend connection.
- [**collection_exists**](#agrag.vectordb.WeaviateVectorStore.collection_exists) – Report whether a collection exists.
- [**count**](#agrag.vectordb.WeaviateVectorStore.count) – Count records in a collection.
- [**delete**](#agrag.vectordb.WeaviateVectorStore.delete) – Delete records by id.
- [**delete_collection**](#agrag.vectordb.WeaviateVectorStore.delete_collection) – Delete a collection and all its objects.
- [**ensure_collection**](#agrag.vectordb.WeaviateVectorStore.ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag.vectordb.WeaviateVectorStore.hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag.vectordb.WeaviateVectorStore.initialize) – Open the connection and check authentication.
- [**retrieve**](#agrag.vectordb.WeaviateVectorStore.retrieve) – Fetch records by id.
- [**scroll**](#agrag.vectordb.WeaviateVectorStore.scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag.vectordb.WeaviateVectorStore.search) – Search by dense vector only.
- [**upsert**](#agrag.vectordb.WeaviateVectorStore.upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[WeaviateSettings](#agrag.vectordb.settings.WeaviateSettings) | None</code>) – Weaviate connection settings. Defaults to
  `WeaviateSettings()`.
- **client** (<code>[Any](#typing.Any) | None</code>) – A pre-built Weaviate async client, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.

##### `agrag.vectordb.WeaviateVectorStore.close`

```python
close() -> None
```

Release the backend connection.

##### `agrag.vectordb.WeaviateVectorStore.collection_exists`

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

**Returns:**

- <code>[bool](#bool)</code> – `True` if the collection exists.

##### `agrag.vectordb.WeaviateVectorStore.count`

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to count.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>[int](#int)</code> – The number of matching records.

##### `agrag.vectordb.WeaviateVectorStore.delete`

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to delete from.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to delete.

##### `agrag.vectordb.WeaviateVectorStore.delete_collection`

```python
delete_collection(name:str) -> None
```

Delete a collection and all its objects.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

##### `agrag.vectordb.WeaviateVectorStore.ensure_collection`

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension. Weaviate stores it on each
  vector, so a mismatch surfaces at write time, not here.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>[bool](#bool)</code>) – No-op for Weaviate, which needs no sparse provisioning.

##### `agrag.vectordb.WeaviateVectorStore.hybrid_search`

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **query_text** (<code>[str](#str)</code>) – The query text, matched by keyword/BM25.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.
- **alpha** (<code>[float](#float)</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The fused hits, highest score first.

##### `agrag.vectordb.WeaviateVectorStore.initialize`

```python
initialize() -> None
```

Open the connection and check authentication.

##### `agrag.vectordb.WeaviateVectorStore.retrieve`

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to fetch.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – ids.

##### `agrag.vectordb.WeaviateVectorStore.scroll`

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **limit** (<code>[int](#int)</code>) – The maximum number of records per page.
- **page_offset** (<code>[str](#str) | None</code>) – The cursor id from a previous `scroll` call.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.
- **with_vectors** (<code>[bool](#bool)</code>) – Whether to return each record's vector.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The page of records and the next page cursor, or `None` at the
- <code>[str](#str) | None</code> – end.

##### `agrag.vectordb.WeaviateVectorStore.search`

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

##### `agrag.vectordb.WeaviateVectorStore.upsert`

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Write or overwrite records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to write to.
- **records** (<code>[Sequence](#collections.abc.Sequence)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>[int](#int)</code>) – The number of records per backend write call.

#### `agrag.vectordb.base`

The VectorStore abstraction and its build shortcut.

**Classes:**

- [**VectorStore**](#agrag.vectordb.base.VectorStore) – A vector database backend: collection lifecycle, writes, and search.

##### `agrag.vectordb.base.VectorStore`

Bases: <code>[ABC](#abc.ABC)</code>

A vector database backend: collection lifecycle, writes, and search.

**Functions:**

- [**close**](#agrag.vectordb.base.VectorStore.close) – Release the backend connection.
- [**collection_exists**](#agrag.vectordb.base.VectorStore.collection_exists) – Report whether a collection exists.
- [**count**](#agrag.vectordb.base.VectorStore.count) – Count records in a collection.
- [**delete**](#agrag.vectordb.base.VectorStore.delete) – Delete records by id.
- [**delete_collection**](#agrag.vectordb.base.VectorStore.delete_collection) – Delete a collection and all its points.
- [**ensure_collection**](#agrag.vectordb.base.VectorStore.ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag.vectordb.base.VectorStore.hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag.vectordb.base.VectorStore.initialize) – Check connectivity and authentication.
- [**retrieve**](#agrag.vectordb.base.VectorStore.retrieve) – Fetch records by id.
- [**scroll**](#agrag.vectordb.base.VectorStore.scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag.vectordb.base.VectorStore.search) – Search by dense vector only.
- [**upsert**](#agrag.vectordb.base.VectorStore.upsert) – Write or overwrite records in a collection.

###### `agrag.vectordb.base.VectorStore.close`

```python
close() -> None
```

Release the backend connection.

###### `agrag.vectordb.base.VectorStore.collection_exists`

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

**Returns:**

- <code>[bool](#bool)</code> – `True` if the collection exists.

###### `agrag.vectordb.base.VectorStore.count`

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to count.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.

**Returns:**

- <code>[int](#int)</code> – The number of matching records.

###### `agrag.vectordb.base.VectorStore.delete`

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to delete from.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to delete.

###### `agrag.vectordb.base.VectorStore.delete_collection`

```python
delete_collection(name:str) -> None
```

Delete a collection and all its points.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

###### `agrag.vectordb.base.VectorStore.ensure_collection`

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension. If the collection already
  exists with a different dimension, this raises.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>[bool](#bool)</code>) – Whether to additionally provision the sparse-vector
  configuration hybrid search needs. Ignored by backends that
  need no such provisioning.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag.vectordb.errors.CollectionDimensionMismatchError)</code> – The collection exists with a
  different dimension than `dimensions`.

###### `agrag.vectordb.base.VectorStore.hybrid_search`

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search. Must have been created with
  `ensure_collection(..., hybrid=True)`.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **query_text** (<code>[str](#str)</code>) – The query text, matched by keyword/BM25.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
- **alpha** (<code>[float](#float)</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword. Weaviate and Milvus apply this weight natively.
  Qdrant's native fusion (Reciprocal Rank Fusion) has no
  continuous weight, so it applies `alpha` by blending two
  independently-scored, min-max normalized result sets instead
  of a single native fused call.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The fused hits, highest score first.

###### `agrag.vectordb.base.VectorStore.initialize`

```python
initialize() -> None
```

Check connectivity and authentication.

**Raises:**

- <code>[VectorStoreError](#agrag.vectordb.errors.VectorStoreError)</code> – The backend is unreachable, or the credentials
  are rejected.

###### `agrag.vectordb.base.VectorStore.retrieve`

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to fetch.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – ids.

###### `agrag.vectordb.base.VectorStore.scroll`

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **limit** (<code>[int](#int)</code>) – The maximum number of records per page.
- **page_offset** (<code>[str](#str) | None</code>) – The offset from a previous `scroll` call, or
  `None` to start at the beginning.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
- **with_vectors** (<code>[bool](#bool)</code>) – Whether to return each record's vector.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The page of records and the next page offset, or `None` at the
- <code>[str](#str) | None</code> – end.

###### `agrag.vectordb.base.VectorStore.search`

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

###### `agrag.vectordb.base.VectorStore.upsert`

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Write or overwrite records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to write to.
- **records** (<code>[Sequence](#collections.abc.Sequence)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>[int](#int)</code>) – The number of records per backend write call.

#### `agrag.vectordb.build_vector_store`

```python
build_vector_store(value:VectorStoreName | VectorStore) -> VectorStore
```

Build a vector store from a backend name, or return one unchanged.

**Parameters:**

- **value** (<code>[VectorStoreName](#agrag.vectordb.VectorStoreName) | [VectorStore](#agrag.vectordb.base.VectorStore)</code>) – `"qdrant"` or `"weaviate"`, or an already-constructed
  `VectorStore` for full control over settings.

**Returns:**

- <code>[VectorStore](#agrag.vectordb.base.VectorStore)</code> – A ready-to-use vector store.

#### `agrag.vectordb.errors`

Errors that the vector-store layer raises.

**Classes:**

- [**CollectionDimensionMismatchError**](#agrag.vectordb.errors.CollectionDimensionMismatchError) – A collection already exists with a different embedding dimension.
- [**VectorStoreError**](#agrag.vectordb.errors.VectorStoreError) – The base class for every vector-store error.
- [**VectorStoreMissingExtraError**](#agrag.vectordb.errors.VectorStoreMissingExtraError) – A vector store exists, but its package extra is not installed.

##### `agrag.vectordb.errors.CollectionDimensionMismatchError`

```python
CollectionDimensionMismatchError(*, expected:int, actual:int) -> None
```

Bases: <code>[VectorStoreError](#agrag.vectordb.errors.VectorStoreError)</code>

A collection already exists with a different embedding dimension.

**Attributes:**

- [**expected**](#agrag.vectordb.errors.CollectionDimensionMismatchError.expected) – The dimension the collection was created with.
- [**actual**](#agrag.vectordb.errors.CollectionDimensionMismatchError.actual) – The dimension the caller requested.

###### `agrag.vectordb.errors.CollectionDimensionMismatchError.actual`

```python
actual = actual
```

###### `agrag.vectordb.errors.CollectionDimensionMismatchError.expected`

```python
expected = expected
```

##### `agrag.vectordb.errors.VectorStoreError`

Bases: <code>[Exception](#Exception)</code>

The base class for every vector-store error.

##### `agrag.vectordb.errors.VectorStoreMissingExtraError`

```python
VectorStoreMissingExtraError(extra:str) -> None
```

Bases: <code>[VectorStoreError](#agrag.vectordb.errors.VectorStoreError)</code>

A vector store exists, but its package extra is not installed.

**Attributes:**

- [**extra**](#agrag.vectordb.errors.VectorStoreMissingExtraError.extra) – The name of the package extra to install.

###### `agrag.vectordb.errors.VectorStoreMissingExtraError.extra`

```python
extra = extra
```

#### `agrag.vectordb.milvus`

Milvus vector-store backend.

**Classes:**

- [**MilvusVectorStore**](#agrag.vectordb.milvus.MilvusVectorStore) – A `VectorStore` backed by Milvus, including native hybrid search.

**Attributes:**

- [**MAX_RESPONSE_LIMIT**](#agrag.vectordb.milvus.MAX_RESPONSE_LIMIT) –

##### `agrag.vectordb.milvus.MAX_RESPONSE_LIMIT`

```python
MAX_RESPONSE_LIMIT = 16384
```

##### `agrag.vectordb.milvus.MilvusVectorStore`

```python
MilvusVectorStore(*, settings:MilvusSettings | None = None, client:Any | None = None) -> None
```

Bases: <code>[VectorStore](#agrag.vectordb.base.VectorStore)</code>

A `VectorStore` backed by Milvus, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Milvus performs BM25 server-side, so hybrid
search needs no client-side sparse embedder; the sparse vector is computed
by a Milvus `Function` from the `text` field on write and at query time.

**Functions:**

- [**close**](#agrag.vectordb.milvus.MilvusVectorStore.close) – Release the backend connection.
- [**collection_exists**](#agrag.vectordb.milvus.MilvusVectorStore.collection_exists) – Report whether a collection exists.
- [**count**](#agrag.vectordb.milvus.MilvusVectorStore.count) – Count records in a collection.
- [**delete**](#agrag.vectordb.milvus.MilvusVectorStore.delete) – Delete records by id.
- [**delete_collection**](#agrag.vectordb.milvus.MilvusVectorStore.delete_collection) – Delete a collection and all its entities.
- [**ensure_collection**](#agrag.vectordb.milvus.MilvusVectorStore.ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag.vectordb.milvus.MilvusVectorStore.hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag.vectordb.milvus.MilvusVectorStore.initialize) – Check connectivity and authentication.
- [**retrieve**](#agrag.vectordb.milvus.MilvusVectorStore.retrieve) – Fetch records by id.
- [**scroll**](#agrag.vectordb.milvus.MilvusVectorStore.scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag.vectordb.milvus.MilvusVectorStore.search) – Search by dense vector only.
- [**upsert**](#agrag.vectordb.milvus.MilvusVectorStore.upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[MilvusSettings](#agrag.vectordb.settings.MilvusSettings) | None</code>) – Milvus connection settings. Defaults to
  `MilvusSettings()`.
- **client** (<code>[Any](#typing.Any) | None</code>) – A pre-built `AsyncMilvusClient`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.

###### `agrag.vectordb.milvus.MilvusVectorStore.close`

```python
close() -> None
```

Release the backend connection.

###### `agrag.vectordb.milvus.MilvusVectorStore.collection_exists`

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

**Returns:**

- <code>[bool](#bool)</code> – `True` if the collection exists.

###### `agrag.vectordb.milvus.MilvusVectorStore.count`

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to count.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on scalar fields.

**Returns:**

- <code>[int](#int)</code> – The number of matching records.

###### `agrag.vectordb.milvus.MilvusVectorStore.delete`

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to delete from.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to delete.

###### `agrag.vectordb.milvus.MilvusVectorStore.delete_collection`

```python
delete_collection(name:str) -> None
```

Delete a collection and all its entities.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

###### `agrag.vectordb.milvus.MilvusVectorStore.ensure_collection`

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

Milvus performs BM25 server-side, so the sparse field and its `Function`
are always provisioned; the `hybrid` flag is accepted for interface
parity but is a no-op here.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>[bool](#bool)</code>) – Accepted for interface parity; ignored by Milvus.

###### `agrag.vectordb.milvus.MilvusVectorStore.hybrid_search`

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

Fusion uses Milvus's native weighted reranker, which normalizes each
request's scores before applying `alpha`.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **query_text** (<code>[str](#str)</code>) – The query text, matched by BM25.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on scalar fields.
- **alpha** (<code>[float](#float)</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The fused hits, highest score first.

###### `agrag.vectordb.milvus.MilvusVectorStore.initialize`

```python
initialize() -> None
```

Check connectivity and authentication.

###### `agrag.vectordb.milvus.MilvusVectorStore.retrieve`

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to fetch.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – ids.

###### `agrag.vectordb.milvus.MilvusVectorStore.scroll`

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **limit** (<code>[int](#int)</code>) – The maximum number of records per page.
- **page_offset** (<code>[str](#str) | None</code>) – The numeric offset from a previous `scroll` call.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on scalar fields.
- **with_vectors** (<code>[bool](#bool)</code>) – Whether to return each record's vector.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The page of records and the next page offset, or `None` at the
- <code>[str](#str) | None</code> – end.

###### `agrag.vectordb.milvus.MilvusVectorStore.search`

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on scalar fields.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

###### `agrag.vectordb.milvus.MilvusVectorStore.upsert`

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Write or overwrite records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to write to.
- **records** (<code>[Sequence](#collections.abc.Sequence)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>[int](#int)</code>) – The number of records per backend write call.

#### `agrag.vectordb.qdrant`

Qdrant vector-store backend.

**Classes:**

- [**QdrantVectorStore**](#agrag.vectordb.qdrant.QdrantVectorStore) – A `VectorStore` backed by Qdrant, including native hybrid search.

##### `agrag.vectordb.qdrant.QdrantVectorStore`

```python
QdrantVectorStore(*, settings:QdrantSettings | None = None, sparse_embedder:SparseEmbedder | None = None, client:Any | None = None) -> None
```

Bases: <code>[VectorStore](#agrag.vectordb.base.VectorStore)</code>

A `VectorStore` backed by Qdrant, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Hybrid search builds its sparse query with a
`SparseEmbedder` that defaults to FastEmbed BM25 and loads only when a
hybrid call first runs, not at construction.

**Functions:**

- [**close**](#agrag.vectordb.qdrant.QdrantVectorStore.close) – Release the backend connection.
- [**collection_exists**](#agrag.vectordb.qdrant.QdrantVectorStore.collection_exists) – Report whether a collection exists.
- [**count**](#agrag.vectordb.qdrant.QdrantVectorStore.count) – Count records in a collection.
- [**delete**](#agrag.vectordb.qdrant.QdrantVectorStore.delete) – Delete records by id.
- [**delete_collection**](#agrag.vectordb.qdrant.QdrantVectorStore.delete_collection) – Delete a collection and all its points.
- [**ensure_collection**](#agrag.vectordb.qdrant.QdrantVectorStore.ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag.vectordb.qdrant.QdrantVectorStore.hybrid_search) – Search by dense vector and keyword text, fused by a weighted blend.
- [**initialize**](#agrag.vectordb.qdrant.QdrantVectorStore.initialize) – Check connectivity and authentication.
- [**retrieve**](#agrag.vectordb.qdrant.QdrantVectorStore.retrieve) – Fetch records by id.
- [**scroll**](#agrag.vectordb.qdrant.QdrantVectorStore.scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag.vectordb.qdrant.QdrantVectorStore.search) – Search by dense vector only.
- [**upsert**](#agrag.vectordb.qdrant.QdrantVectorStore.upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[QdrantSettings](#agrag.vectordb.settings.QdrantSettings) | None</code>) – Qdrant connection settings. Defaults to
  `QdrantSettings()`.
- **sparse_embedder** (<code>[SparseEmbedder](#agrag.embedding.sparse_base.SparseEmbedder) | None</code>) – The sparse embedder hybrid search uses. Defaults to
  a lazily-built `FastEmbedBM25Embedder`.
- **client** (<code>[Any](#typing.Any) | None</code>) – A pre-built `AsyncQdrantClient`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.

###### `agrag.vectordb.qdrant.QdrantVectorStore.close`

```python
close() -> None
```

Release the backend connection.

###### `agrag.vectordb.qdrant.QdrantVectorStore.collection_exists`

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

**Returns:**

- <code>[bool](#bool)</code> – `True` if the collection exists.

###### `agrag.vectordb.qdrant.QdrantVectorStore.count`

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to count.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>[int](#int)</code> – The number of matching records.

###### `agrag.vectordb.qdrant.QdrantVectorStore.delete`

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to delete from.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to delete.

###### `agrag.vectordb.qdrant.QdrantVectorStore.delete_collection`

```python
delete_collection(name:str) -> None
```

Delete a collection and all its points.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

###### `agrag.vectordb.qdrant.QdrantVectorStore.ensure_collection`

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>[bool](#bool)</code>) – Whether to provision the named sparse vector hybrid search
  needs.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag.vectordb.errors.CollectionDimensionMismatchError)</code> – The collection exists with a
  different dimension than `dimensions`.

###### `agrag.vectordb.qdrant.QdrantVectorStore.hybrid_search`

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text, fused by a weighted blend.

Qdrant's native fusion methods (RRF, DBSF) have no continuous
dense/keyword weight, so this runs the dense and sparse (BM25)
searches independently, min-max normalizes each result set's scores
to `[0, 1]`, then combines them per id as
`alpha * dense + (1 - alpha) * sparse`. Each side fetches a wider
candidate pool than `limit` so a document strong on only one signal
still has a chance to reach the blended top results.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **query_text** (<code>[str](#str)</code>) – The query text, matched by BM25.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.
- **alpha** (<code>[float](#float)</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The blended hits, highest combined score first.

###### `agrag.vectordb.qdrant.QdrantVectorStore.initialize`

```python
initialize() -> None
```

Check connectivity and authentication.

###### `agrag.vectordb.qdrant.QdrantVectorStore.retrieve`

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to fetch.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – ids.

###### `agrag.vectordb.qdrant.QdrantVectorStore.scroll`

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **limit** (<code>[int](#int)</code>) – The maximum number of records per page.
- **page_offset** (<code>[str](#str) | None</code>) – The offset from a previous `scroll` call.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.
- **with_vectors** (<code>[bool](#bool)</code>) – Whether to return each record's vector.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The page of records and the next page offset, or `None` at the
- <code>[str](#str) | None</code> – end.

###### `agrag.vectordb.qdrant.QdrantVectorStore.search`

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

###### `agrag.vectordb.qdrant.QdrantVectorStore.upsert`

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Write or overwrite records in a collection.

When `collection` was created with `ensure_collection(..., hybrid=True)`, each record's `payload["text"]` is also
sparse-embedded and stored under the named sparse vector, so
`hybrid_search`'s keyword arm has real vectors to match. A record
with no `text` payload key gets an empty sparse vector and only
ever surfaces through the dense side of a hybrid search.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to write to.
- **records** (<code>[Sequence](#collections.abc.Sequence)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>[int](#int)</code>) – The number of records per backend write call.

#### `agrag.vectordb.settings`

Settings for vector-store backends.

**Classes:**

- [**MilvusSettings**](#agrag.vectordb.settings.MilvusSettings) – Milvus connection configuration.
- [**QdrantSettings**](#agrag.vectordb.settings.QdrantSettings) – Qdrant connection configuration.
- [**WeaviateSettings**](#agrag.vectordb.settings.WeaviateSettings) – Weaviate connection configuration.

##### `agrag.vectordb.settings.MilvusSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Milvus connection configuration.

**Attributes:**

- [**uri**](#agrag.vectordb.settings.MilvusSettings.uri) (<code>[str](#str)</code>) – The Milvus endpoint URI. Env: `MILVUS_URI`.
- [**token**](#agrag.vectordb.settings.MilvusSettings.token) (<code>[str](#str)</code>) – The Milvus auth token. Empty string for an unauthenticated
  instance. Env: `MILVUS_TOKEN`.

###### `agrag.vectordb.settings.MilvusSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='MILVUS_', env_file='.env', extra='ignore')
```

###### `agrag.vectordb.settings.MilvusSettings.token`

```python
token: str = ''
```

###### `agrag.vectordb.settings.MilvusSettings.uri`

```python
uri: str = 'http://localhost:19530'
```

##### `agrag.vectordb.settings.QdrantSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Qdrant connection configuration.

**Attributes:**

- [**url**](#agrag.vectordb.settings.QdrantSettings.url) (<code>[str](#str)</code>) – The Qdrant endpoint URL. Env: `QDRANT_URL`.
- [**api_key**](#agrag.vectordb.settings.QdrantSettings.api_key) (<code>[str](#str)</code>) – The Qdrant API key. Env: `QDRANT_API_KEY`.

###### `agrag.vectordb.settings.QdrantSettings.api_key`

```python
api_key: str = ''
```

###### `agrag.vectordb.settings.QdrantSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='QDRANT_', env_file='.env', extra='ignore')
```

###### `agrag.vectordb.settings.QdrantSettings.url`

```python
url: str = 'http://localhost:6333'
```

##### `agrag.vectordb.settings.WeaviateSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Weaviate connection configuration.

**Attributes:**

- [**mode**](#agrag.vectordb.settings.WeaviateSettings.mode) (<code>[Literal](#typing.Literal)['cloud', 'custom']</code>) – `"cloud"` connects to Weaviate Cloud. `"custom"` connects to
  a self-hosted instance (used by integration tests against the local
  Docker Compose instance) — an explicit field, not inferred from the
  URL, since inference caused real connection bugs in surveyed
  reference implementations. Env: `WEAVIATE_MODE`.
- [**url**](#agrag.vectordb.settings.WeaviateSettings.url) (<code>[str](#str)</code>) – The Weaviate endpoint URL. For `"cloud"`, the cluster URL. For
  `"custom"`, the full host URL. Env: `WEAVIATE_URL`.
- [**api_key**](#agrag.vectordb.settings.WeaviateSettings.api_key) (<code>[str](#str)</code>) – The Weaviate API key. Env: `WEAVIATE_API_KEY`.
- [**grpc_port**](#agrag.vectordb.settings.WeaviateSettings.grpc_port) (<code>[int](#int)</code>) – The gRPC port, used by `"custom"` mode only (`"cloud"`
  mode infers it). Env: `WEAVIATE_GRPC_PORT`.

###### `agrag.vectordb.settings.WeaviateSettings.api_key`

```python
api_key: str = ''
```

###### `agrag.vectordb.settings.WeaviateSettings.grpc_port`

```python
grpc_port: int = 50051
```

###### `agrag.vectordb.settings.WeaviateSettings.mode`

```python
mode: Literal['cloud', 'custom'] = 'cloud'
```

###### `agrag.vectordb.settings.WeaviateSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='WEAVIATE_', env_file='.env', extra='ignore')
```

###### `agrag.vectordb.settings.WeaviateSettings.url`

```python
url: str = 'http://localhost:8080'
```

#### `agrag.vectordb.weaviate`

Weaviate vector-store backend.

**Classes:**

- [**WeaviateVectorStore**](#agrag.vectordb.weaviate.WeaviateVectorStore) – A `VectorStore` backed by Weaviate, including native hybrid search.

##### `agrag.vectordb.weaviate.WeaviateVectorStore`

```python
WeaviateVectorStore(*, settings:WeaviateSettings | None = None, client:Any | None = None) -> None
```

Bases: <code>[VectorStore](#agrag.vectordb.base.VectorStore)</code>

A `VectorStore` backed by Weaviate, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Weaviate does its own server-side BM25, so
hybrid search needs no client-side sparse embedder.

**Functions:**

- [**close**](#agrag.vectordb.weaviate.WeaviateVectorStore.close) – Release the backend connection.
- [**collection_exists**](#agrag.vectordb.weaviate.WeaviateVectorStore.collection_exists) – Report whether a collection exists.
- [**count**](#agrag.vectordb.weaviate.WeaviateVectorStore.count) – Count records in a collection.
- [**delete**](#agrag.vectordb.weaviate.WeaviateVectorStore.delete) – Delete records by id.
- [**delete_collection**](#agrag.vectordb.weaviate.WeaviateVectorStore.delete_collection) – Delete a collection and all its objects.
- [**ensure_collection**](#agrag.vectordb.weaviate.WeaviateVectorStore.ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag.vectordb.weaviate.WeaviateVectorStore.hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag.vectordb.weaviate.WeaviateVectorStore.initialize) – Open the connection and check authentication.
- [**retrieve**](#agrag.vectordb.weaviate.WeaviateVectorStore.retrieve) – Fetch records by id.
- [**scroll**](#agrag.vectordb.weaviate.WeaviateVectorStore.scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag.vectordb.weaviate.WeaviateVectorStore.search) – Search by dense vector only.
- [**upsert**](#agrag.vectordb.weaviate.WeaviateVectorStore.upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[WeaviateSettings](#agrag.vectordb.settings.WeaviateSettings) | None</code>) – Weaviate connection settings. Defaults to
  `WeaviateSettings()`.
- **client** (<code>[Any](#typing.Any) | None</code>) – A pre-built Weaviate async client, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.close`

```python
close() -> None
```

Release the backend connection.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.collection_exists`

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

**Returns:**

- <code>[bool](#bool)</code> – `True` if the collection exists.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.count`

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to count.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>[int](#int)</code> – The number of matching records.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.delete`

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to delete from.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to delete.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.delete_collection`

```python
delete_collection(name:str) -> None
```

Delete a collection and all its objects.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.ensure_collection`

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension. Weaviate stores it on each
  vector, so a mismatch surfaces at write time, not here.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>[bool](#bool)</code>) – No-op for Weaviate, which needs no sparse provisioning.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.hybrid_search`

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **query_text** (<code>[str](#str)</code>) – The query text, matched by keyword/BM25.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.
- **alpha** (<code>[float](#float)</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The fused hits, highest score first.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.initialize`

```python
initialize() -> None
```

Open the connection and check authentication.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.retrieve`

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to fetch.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – ids.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.scroll`

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **limit** (<code>[int](#int)</code>) – The maximum number of records per page.
- **page_offset** (<code>[str](#str) | None</code>) – The cursor id from a previous `scroll` call.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.
- **with_vectors** (<code>[bool](#bool)</code>) – Whether to return each record's vector.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The page of records and the next page cursor, or `None` at the
- <code>[str](#str) | None</code> – end.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.search`

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.upsert`

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Write or overwrite records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to write to.
- **records** (<code>[Sequence](#collections.abc.Sequence)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>[int](#int)</code>) – The number of records per backend write call.
