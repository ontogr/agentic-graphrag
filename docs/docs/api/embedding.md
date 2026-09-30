---
title: agrag.embedding
sidebar_position: 5
---

## `agrag.embedding` \{#agrag-embedding}

Text embedding: turn strings into dense vectors.

**Modules:**

- [**base**](#agrag-embedding-base) – The Embedder and EmbeddingCache protocols.
- [**errors**](#agrag-embedding-errors) – Errors that the embedding layer raises.
- [**fastembed_bm25**](#agrag-embedding-fastembed_bm25) – BM25 sparse embedder backed by FastEmbed.
- [**sentence_transformers**](#agrag-embedding-sentence_transformers) – Sentence-transformers embedder implementation.
- [**settings**](#agrag-embedding-settings) – Settings for the sentence-transformers embedder.
- [**sparse_base**](#agrag-embedding-sparse_base) – Sparse lexical vectors and the sparse embedder protocol.

**Classes:**

- [**Embedder**](#agrag-embedding-Embedder) – A component that turns text into dense embedding vectors.
- [**EmbeddingSettings**](#agrag-embedding-EmbeddingSettings) – Sentence-transformers embedder configuration.
- [**FastEmbedBM25Embedder**](#agrag-embedding-FastEmbedBM25Embedder) – A sparse BM25 embedder built on FastEmbed.
- [**SentenceTransformerEmbedder**](#agrag-embedding-SentenceTransformerEmbedder) – An embedder backed by sentence-transformers.
- [**SparseEmbedder**](#agrag-embedding-SparseEmbedder) – A component that turns text into sparse lexical vectors, for hybrid search.
- [**SparseVector**](#agrag-embedding-SparseVector) – A sparse vector: nonzero indices and their values.

**Functions:**

- [**build_embedder**](#agrag-embedding-build_embedder) – Build an embedder from a model name, or return an embedder unchanged.

### `agrag.embedding.Embedder` \{#agrag-embedding-Embedder}

Bases: <code>ABC</code>

A component that turns text into dense embedding vectors.

**Functions:**

- [**dimensions**](#agrag-embedding-Embedder-dimensions) – Return the dimension of the vectors this embedder produces.
- [**embed**](#agrag-embedding-Embedder-embed) – Embed a batch of texts.
- [**embed_one**](#agrag-embedding-Embedder-embed_one) – Embed a single text.

**Attributes:**

- [**distance**](#agrag-embedding-Embedder-distance) (<code>[Distance](common.md#agrag-common-data_models-vector_record-Distance)</code>) – Return the distance metric for vector indexes created for this embedder.
- [**model**](#agrag-embedding-Embedder-model) (<code>str</code>) –

#### `agrag.embedding.Embedder.dimensions` \{#agrag-embedding-Embedder-dimensions}

```python
dimensions() -> int
```

Return the dimension of the vectors this embedder produces.

Async because a lazily-loaded embedder may need to load its model to
answer, and that load must go through the same worker-thread/lock
path `embed` uses rather than blocking the event loop.

#### `agrag.embedding.Embedder.distance` \{#agrag-embedding-Embedder-distance}

```python
distance: Distance
```

Return the distance metric for vector indexes created for this embedder.

Defaults to cosine, which matches normalized sentence-transformer models.
Concrete embedders may override when their vectors use a different
metric.

#### `agrag.embedding.Embedder.embed` \{#agrag-embedding-Embedder-embed}

```python
embed(texts:Sequence[str]) -> list[list[float]]
```

Embed a batch of texts.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The texts to embed, in order.

**Returns:**

- <code>list\[list\[float\]\]</code> – One vector per input text, in the same order.

#### `agrag.embedding.Embedder.embed_one` \{#agrag-embedding-Embedder-embed_one}

```python
embed_one(text:str) -> list[float]
```

Embed a single text.

**Parameters:**

- **text** (<code>str</code>) – The text to embed.

**Returns:**

- <code>list\[float\]</code> – The text's embedding vector.

#### `agrag.embedding.Embedder.model` \{#agrag-embedding-Embedder-model}

```python
model: str
```

### `agrag.embedding.EmbeddingSettings` \{#agrag-embedding-EmbeddingSettings}

Bases: <code>BaseSettings</code>

Sentence-transformers embedder configuration.

All fields are overridable via environment variables with the
`EMBEDDING_` prefix.

**Attributes:**

- [**model**](#agrag-embedding-EmbeddingSettings-model) (<code>str</code>) – The sentence-transformers model name or path. Env: `EMBEDDING_MODEL`.
- [**device**](#agrag-embedding-EmbeddingSettings-device) (<code>str | None</code>) – The device to load the model on, such as `"cpu"` or `"cuda"`.
  `None` uses sentence-transformers' own default detection. Env:
  `EMBEDDING_DEVICE`.
- [**normalize**](#agrag-embedding-EmbeddingSettings-normalize) (<code>bool</code>) – Whether to L2-normalize output vectors. Env: `EMBEDDING_NORMALIZE`.
- [**batch_size**](#agrag-embedding-EmbeddingSettings-batch_size) (<code>int</code>) – The number of texts encoded per `model.encode` call. Env:
  `EMBEDDING_BATCH_SIZE`.
- [**cache_folder**](#agrag-embedding-EmbeddingSettings-cache_folder) (<code>str | None</code>) – Where sentence-transformers caches downloaded models.
  `None` uses the library default. Env: `EMBEDDING_CACHE_FOLDER`.

#### `agrag.embedding.EmbeddingSettings.batch_size` \{#agrag-embedding-EmbeddingSettings-batch_size}

```python
batch_size: int = 32
```

#### `agrag.embedding.EmbeddingSettings.cache_folder` \{#agrag-embedding-EmbeddingSettings-cache_folder}

```python
cache_folder: str | None = None
```

#### `agrag.embedding.EmbeddingSettings.device` \{#agrag-embedding-EmbeddingSettings-device}

```python
device: str | None = None
```

#### `agrag.embedding.EmbeddingSettings.model` \{#agrag-embedding-EmbeddingSettings-model}

```python
model: str = 'ibm-granite/granite-embedding-small-english-r2'
```

#### `agrag.embedding.EmbeddingSettings.model_config` \{#agrag-embedding-EmbeddingSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='EMBEDDING_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

#### `agrag.embedding.EmbeddingSettings.normalize` \{#agrag-embedding-EmbeddingSettings-normalize}

```python
normalize: bool = True
```

### `agrag.embedding.FastEmbedBM25Embedder` \{#agrag-embedding-FastEmbedBM25Embedder}

```python
FastEmbedBM25Embedder(*, model:str | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[SparseEmbedder](#agrag-embedding-sparse_base-SparseEmbedder)</code>

A sparse BM25 embedder built on FastEmbed.

The model loads lazily on first `embed`, so constructing the embedder
does not download weights. Each blocking call into FastEmbed runs in a
worker thread, keeping the event loop free. FastEmbed ships with the
`qdrant` extra, so a clean install without that extra raises
`EmbeddingMissingExtraError` rather than `ImportError`.

**Functions:**

- [**embed**](#agrag-embedding-FastEmbedBM25Embedder-embed) – Embed a batch of documents into BM25 sparse vectors.
- [**query_embed**](#agrag-embedding-FastEmbedBM25Embedder-query_embed) – Embed a batch of search queries into BM25 sparse vectors.

**Attributes:**

- [**model**](#agrag-embedding-FastEmbedBM25Embedder-model) (<code>str</code>) – The configured model name, or the FastEmbed default when unset.

**Parameters:**

- **model** (<code>str | None</code>) – The FastEmbed BM25 model name. Defaults to FastEmbed's
  built-in BM25 model.
- **tracer** (<code>Tracer | None</code>) – Opens every span this embedder's methods produce.

#### `agrag.embedding.FastEmbedBM25Embedder.embed` \{#agrag-embedding-FastEmbedBM25Embedder-embed}

```python
embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of documents into BM25 sparse vectors.

Applies FastEmbed's document-side term-frequency and length
normalization weighting. Use `query_embed` for search queries.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The document texts to embed, in order.

**Returns:**

- <code>list\[[SparseVector](#agrag-embedding-sparse_base-SparseVector)\]</code> – One sparse vector per input text, in the same order.

#### `agrag.embedding.FastEmbedBM25Embedder.model` \{#agrag-embedding-FastEmbedBM25Embedder-model}

```python
model: str
```

The configured model name, or the FastEmbed default when unset.

#### `agrag.embedding.FastEmbedBM25Embedder.query_embed` \{#agrag-embedding-FastEmbedBM25Embedder-query_embed}

```python
query_embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of search queries into BM25 sparse vectors.

Uses FastEmbed's `query_embed`, which assigns each unique query
term a uniform weight of `1.0` rather than the document-side
term-frequency and length-normalization weighting `embed` applies;
IDF weighting is applied separately by the sparse index's
`Modifier.IDF` at query time.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The query texts to embed, in order.

**Returns:**

- <code>list\[[SparseVector](#agrag-embedding-sparse_base-SparseVector)\]</code> – One sparse vector per input text, in the same order.

### `agrag.embedding.SentenceTransformerEmbedder` \{#agrag-embedding-SentenceTransformerEmbedder}

```python
SentenceTransformerEmbedder(*, settings:EmbeddingSettings | None = None, cache:EmbeddingCache | None = None, model:object | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Embedder](#agrag-embedding-base-Embedder)</code>

An embedder backed by sentence-transformers.

The model loads lazily on first `embed`, so constructing the embedder
does not touch the GPU or download weights. Every blocking call into the
model runs in a worker thread (`asyncio.to_thread`), so the event loop
stays free for other work while a large batch encodes.

**Functions:**

- [**dimensions**](#agrag-embedding-SentenceTransformerEmbedder-dimensions) – Return the dimension the loaded model produces.
- [**embed**](#agrag-embedding-SentenceTransformerEmbedder-embed) – Embed a batch of texts, using the cache where possible.
- [**embed_one**](#agrag-embedding-SentenceTransformerEmbedder-embed_one) – Embed a single text.

**Attributes:**

- [**distance**](#agrag-embedding-SentenceTransformerEmbedder-distance) (<code>[Distance](common.md#agrag-common-data_models-vector_record-Distance)</code>) – Return the distance metric for vector indexes created for this embedder.
- [**model**](#agrag-embedding-SentenceTransformerEmbedder-model) (<code>str</code>) – The configured model name.

**Parameters:**

- **settings** (<code>[EmbeddingSettings](#agrag-embedding-settings-EmbeddingSettings) | None</code>) – Embedder configuration. Defaults to `EmbeddingSettings()`.
- **cache** (<code>[EmbeddingCache](#agrag-embedding-base-EmbeddingCache) | None</code>) – An optional content-addressed cache. Defaults to a no-op cache.
- **model** (<code>object | None</code>) – A pre-built sentence-transformers model, for tests. When set,
  `__init__` imports nothing and `embed` calls this object
  directly instead of building one.
- **tracer** (<code>Tracer | None</code>) – Opens every span this embedder's methods produce.

#### `agrag.embedding.SentenceTransformerEmbedder.dimensions` \{#agrag-embedding-SentenceTransformerEmbedder-dimensions}

```python
dimensions() -> int
```

Return the dimension the loaded model produces.

Calling this loads the model the first time, the same
lock-protected, worker-thread path `embed` uses, so it is safe to
call concurrently with `embed` without stalling the event loop or
loading a second copy of the model.

**Raises:**

- <code>[EmbeddingMissingExtraError](#agrag-embedding-errors-EmbeddingMissingExtraError)</code> – sentence-transformers is not installed.

#### `agrag.embedding.SentenceTransformerEmbedder.distance` \{#agrag-embedding-SentenceTransformerEmbedder-distance}

```python
distance: Distance
```

Return the distance metric for vector indexes created for this embedder.

Defaults to cosine, which matches normalized sentence-transformer models.
Concrete embedders may override when their vectors use a different
metric.

#### `agrag.embedding.SentenceTransformerEmbedder.embed` \{#agrag-embedding-SentenceTransformerEmbedder-embed}

```python
embed(texts:Sequence[str]) -> list[list[float]]
```

Embed a batch of texts, using the cache where possible.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The texts to embed, in order.

**Returns:**

- <code>list\[list\[float\]\]</code> – One vector per input text, in the same order.

#### `agrag.embedding.SentenceTransformerEmbedder.embed_one` \{#agrag-embedding-SentenceTransformerEmbedder-embed_one}

```python
embed_one(text:str) -> list[float]
```

Embed a single text.

**Parameters:**

- **text** (<code>str</code>) – The text to embed.

**Returns:**

- <code>list\[float\]</code> – The text's embedding vector.

#### `agrag.embedding.SentenceTransformerEmbedder.model` \{#agrag-embedding-SentenceTransformerEmbedder-model}

```python
model: str
```

The configured model name.

### `agrag.embedding.SparseEmbedder` \{#agrag-embedding-SparseEmbedder}

Bases: <code>ABC</code>

A component that turns text into sparse lexical vectors, for hybrid search.

**Functions:**

- [**embed**](#agrag-embedding-SparseEmbedder-embed) – Embed a batch of documents into sparse vectors.
- [**query_embed**](#agrag-embedding-SparseEmbedder-query_embed) – Embed a batch of search queries into sparse vectors.

**Attributes:**

- [**model**](#agrag-embedding-SparseEmbedder-model) (<code>str</code>) –

#### `agrag.embedding.SparseEmbedder.embed` \{#agrag-embedding-SparseEmbedder-embed}

```python
embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of documents into sparse vectors.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The document texts to embed, in order.

**Returns:**

- <code>list\[[SparseVector](#agrag-embedding-sparse_base-SparseVector)\]</code> – One sparse vector per input text, in the same order.

#### `agrag.embedding.SparseEmbedder.model` \{#agrag-embedding-SparseEmbedder-model}

```python
model: str
```

#### `agrag.embedding.SparseEmbedder.query_embed` \{#agrag-embedding-SparseEmbedder-query_embed}

```python
query_embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of search queries into sparse vectors.

Query-side sparse embedding is not always the same computation as
document-side embedding: BM25, for example, applies term-frequency
and document-length normalization on the document side but only a
uniform per-term weight on the query side, since IDF weighting is
applied by the sparse index at query time instead. Implementations
with no such asymmetry may implement this identically to `embed`.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The query texts to embed, in order.

**Returns:**

- <code>list\[[SparseVector](#agrag-embedding-sparse_base-SparseVector)\]</code> – One sparse vector per input text, in the same order.

### `agrag.embedding.SparseVector` \{#agrag-embedding-SparseVector}

Bases: <code>BaseModel</code>

A sparse vector: nonzero indices and their values.

**Attributes:**

- [**indices**](#agrag-embedding-SparseVector-indices) (<code>list\[int\]</code>) – The positions of nonzero entries.
- [**values**](#agrag-embedding-SparseVector-values) (<code>list\[float\]</code>) – The weight at each index, aligned with `indices`.

#### `agrag.embedding.SparseVector.indices` \{#agrag-embedding-SparseVector-indices}

```python
indices: list[int]
```

#### `agrag.embedding.SparseVector.values` \{#agrag-embedding-SparseVector-values}

```python
values: list[float]
```

### `agrag.embedding.base` \{#agrag-embedding-base}

The Embedder and EmbeddingCache protocols.

**Classes:**

- [**Embedder**](#agrag-embedding-base-Embedder) – A component that turns text into dense embedding vectors.
- [**EmbeddingCache**](#agrag-embedding-base-EmbeddingCache) – A content-addressed cache for embedding vectors.
- [**NullEmbeddingCache**](#agrag-embedding-base-NullEmbeddingCache) – A cache that never stores anything. The default when none is injected.

#### `agrag.embedding.base.Embedder` \{#agrag-embedding-base-Embedder}

Bases: <code>ABC</code>

A component that turns text into dense embedding vectors.

**Functions:**

- [**dimensions**](#agrag-embedding-base-Embedder-dimensions) – Return the dimension of the vectors this embedder produces.
- [**embed**](#agrag-embedding-base-Embedder-embed) – Embed a batch of texts.
- [**embed_one**](#agrag-embedding-base-Embedder-embed_one) – Embed a single text.

**Attributes:**

- [**distance**](#agrag-embedding-base-Embedder-distance) (<code>[Distance](common.md#agrag-common-data_models-vector_record-Distance)</code>) – Return the distance metric for vector indexes created for this embedder.
- [**model**](#agrag-embedding-base-Embedder-model) (<code>str</code>) –

##### `agrag.embedding.base.Embedder.dimensions` \{#agrag-embedding-base-Embedder-dimensions}

```python
dimensions() -> int
```

Return the dimension of the vectors this embedder produces.

Async because a lazily-loaded embedder may need to load its model to
answer, and that load must go through the same worker-thread/lock
path `embed` uses rather than blocking the event loop.

##### `agrag.embedding.base.Embedder.distance` \{#agrag-embedding-base-Embedder-distance}

```python
distance: Distance
```

Return the distance metric for vector indexes created for this embedder.

Defaults to cosine, which matches normalized sentence-transformer models.
Concrete embedders may override when their vectors use a different
metric.

##### `agrag.embedding.base.Embedder.embed` \{#agrag-embedding-base-Embedder-embed}

```python
embed(texts:Sequence[str]) -> list[list[float]]
```

Embed a batch of texts.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The texts to embed, in order.

**Returns:**

- <code>list\[list\[float\]\]</code> – One vector per input text, in the same order.

##### `agrag.embedding.base.Embedder.embed_one` \{#agrag-embedding-base-Embedder-embed_one}

```python
embed_one(text:str) -> list[float]
```

Embed a single text.

**Parameters:**

- **text** (<code>str</code>) – The text to embed.

**Returns:**

- <code>list\[float\]</code> – The text's embedding vector.

##### `agrag.embedding.base.Embedder.model` \{#agrag-embedding-base-Embedder-model}

```python
model: str
```

#### `agrag.embedding.base.EmbeddingCache` \{#agrag-embedding-base-EmbeddingCache}

Bases: <code>ABC</code>

A content-addressed cache for embedding vectors.

`normalize` is part of the cache key alongside `text` and `model`
because it changes the vector an embedder produces for the same text and
model: without it, embedders sharing one cache but configured with
opposite `EmbeddingSettings.normalize` values would read back the wrong
output mode. Any future embedder setting that changes output values must
join this key the same way.

**Functions:**

- [**get**](#agrag-embedding-base-EmbeddingCache-get) – Return the cached vector for `(text, model, normalize)`.
- [**set**](#agrag-embedding-base-EmbeddingCache-set) – Store `vector` under `(text, model, normalize)`.

##### `agrag.embedding.base.EmbeddingCache.get` \{#agrag-embedding-base-EmbeddingCache-get}

```python
get(*, text:str, model:str, normalize:bool) -> list[float] | None
```

Return the cached vector for `(text, model, normalize)`.

**Returns:**

- <code>list\[float\] | None</code> – The cached vector, or `None` on a miss.

##### `agrag.embedding.base.EmbeddingCache.set` \{#agrag-embedding-base-EmbeddingCache-set}

```python
set(*, text:str, model:str, normalize:bool, vector:list[float]) -> None
```

Store `vector` under `(text, model, normalize)`.

#### `agrag.embedding.base.NullEmbeddingCache` \{#agrag-embedding-base-NullEmbeddingCache}

Bases: <code>[EmbeddingCache](#agrag-embedding-base-EmbeddingCache)</code>

A cache that never stores anything. The default when none is injected.

**Functions:**

- [**get**](#agrag-embedding-base-NullEmbeddingCache-get) – Always miss.
- [**set**](#agrag-embedding-base-NullEmbeddingCache-set) – Do nothing.

##### `agrag.embedding.base.NullEmbeddingCache.get` \{#agrag-embedding-base-NullEmbeddingCache-get}

```python
get(*, text:str, model:str, normalize:bool) -> list[float] | None
```

Always miss.

##### `agrag.embedding.base.NullEmbeddingCache.set` \{#agrag-embedding-base-NullEmbeddingCache-set}

```python
set(*, text:str, model:str, normalize:bool, vector:list[float]) -> None
```

Do nothing.

### `agrag.embedding.build_embedder` \{#agrag-embedding-build_embedder}

```python
build_embedder(value:str | Embedder, *, tracer:Tracer | None = None) -> Embedder
```

Build an embedder from a model name, or return an embedder unchanged.

**Parameters:**

- **value** (<code>str | [Embedder](#agrag-embedding-base-Embedder)</code>) – A sentence-transformers model name, such as
  `"ibm-granite/granite-embedding-small-english-r2"` (the default
  model), or an already-constructed `Embedder` for full control
  over device, batching, or caching.
- **tracer** (<code>Tracer | None</code>) – Passed to the newly-built embedder. Not valid together with
  an already-constructed `value` -- that instance's tracer, if
  any, was already fixed at its own construction.

**Returns:**

- <code>[Embedder](#agrag-embedding-base-Embedder)</code> – A ready-to-use embedder.

**Raises:**

- <code>ValueError</code> – `tracer` is given together with an already-constructed
  `value`.

### `agrag.embedding.errors` \{#agrag-embedding-errors}

Errors that the embedding layer raises.

**Classes:**

- [**EmbeddingDimensionMismatchError**](#agrag-embedding-errors-EmbeddingDimensionMismatchError) – A stored collection or index expects a different embedding dimension.
- [**EmbeddingError**](#agrag-embedding-errors-EmbeddingError) – The base class for every embedding error.
- [**EmbeddingMissingExtraError**](#agrag-embedding-errors-EmbeddingMissingExtraError) – An embedder exists, but its package extra is not installed.

#### `agrag.embedding.errors.EmbeddingDimensionMismatchError` \{#agrag-embedding-errors-EmbeddingDimensionMismatchError}

```python
EmbeddingDimensionMismatchError(*, expected:int, actual:int) -> None
```

Bases: <code>[EmbeddingError](#agrag-embedding-errors-EmbeddingError)</code>

A stored collection or index expects a different embedding dimension.

**Attributes:**

- [**expected**](#agrag-embedding-errors-EmbeddingDimensionMismatchError-expected) – The dimension the collection or index was created with.
- [**actual**](#agrag-embedding-errors-EmbeddingDimensionMismatchError-actual) – The dimension the embedder actually produces.

##### `agrag.embedding.errors.EmbeddingDimensionMismatchError.actual` \{#agrag-embedding-errors-EmbeddingDimensionMismatchError-actual}

```python
actual = actual
```

##### `agrag.embedding.errors.EmbeddingDimensionMismatchError.expected` \{#agrag-embedding-errors-EmbeddingDimensionMismatchError-expected}

```python
expected = expected
```

#### `agrag.embedding.errors.EmbeddingError` \{#agrag-embedding-errors-EmbeddingError}

Bases: <code>Exception</code>

The base class for every embedding error.

#### `agrag.embedding.errors.EmbeddingMissingExtraError` \{#agrag-embedding-errors-EmbeddingMissingExtraError}

```python
EmbeddingMissingExtraError(extra:str) -> None
```

Bases: <code>[EmbeddingError](#agrag-embedding-errors-EmbeddingError)</code>

An embedder exists, but its package extra is not installed.

**Attributes:**

- [**extra**](#agrag-embedding-errors-EmbeddingMissingExtraError-extra) – The name of the package extra to install.

##### `agrag.embedding.errors.EmbeddingMissingExtraError.extra` \{#agrag-embedding-errors-EmbeddingMissingExtraError-extra}

```python
extra = extra
```

### `agrag.embedding.fastembed_bm25` \{#agrag-embedding-fastembed_bm25}

BM25 sparse embedder backed by FastEmbed.

**Classes:**

- [**FastEmbedBM25Embedder**](#agrag-embedding-fastembed_bm25-FastEmbedBM25Embedder) – A sparse BM25 embedder built on FastEmbed.

**Attributes:**

- [**DEFAULT_BM25_MODEL**](#agrag-embedding-fastembed_bm25-DEFAULT_BM25_MODEL) –

#### `agrag.embedding.fastembed_bm25.DEFAULT_BM25_MODEL` \{#agrag-embedding-fastembed_bm25-DEFAULT_BM25_MODEL}

```python
DEFAULT_BM25_MODEL = 'Qdrant/bm25'
```

#### `agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder` \{#agrag-embedding-fastembed_bm25-FastEmbedBM25Embedder}

```python
FastEmbedBM25Embedder(*, model:str | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[SparseEmbedder](#agrag-embedding-sparse_base-SparseEmbedder)</code>

A sparse BM25 embedder built on FastEmbed.

The model loads lazily on first `embed`, so constructing the embedder
does not download weights. Each blocking call into FastEmbed runs in a
worker thread, keeping the event loop free. FastEmbed ships with the
`qdrant` extra, so a clean install without that extra raises
`EmbeddingMissingExtraError` rather than `ImportError`.

**Functions:**

- [**embed**](#agrag-embedding-fastembed_bm25-FastEmbedBM25Embedder-embed) – Embed a batch of documents into BM25 sparse vectors.
- [**query_embed**](#agrag-embedding-fastembed_bm25-FastEmbedBM25Embedder-query_embed) – Embed a batch of search queries into BM25 sparse vectors.

**Attributes:**

- [**model**](#agrag-embedding-fastembed_bm25-FastEmbedBM25Embedder-model) (<code>str</code>) – The configured model name, or the FastEmbed default when unset.

**Parameters:**

- **model** (<code>str | None</code>) – The FastEmbed BM25 model name. Defaults to FastEmbed's
  built-in BM25 model.
- **tracer** (<code>Tracer | None</code>) – Opens every span this embedder's methods produce.

##### `agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder.embed` \{#agrag-embedding-fastembed_bm25-FastEmbedBM25Embedder-embed}

```python
embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of documents into BM25 sparse vectors.

Applies FastEmbed's document-side term-frequency and length
normalization weighting. Use `query_embed` for search queries.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The document texts to embed, in order.

**Returns:**

- <code>list\[[SparseVector](#agrag-embedding-sparse_base-SparseVector)\]</code> – One sparse vector per input text, in the same order.

##### `agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder.model` \{#agrag-embedding-fastembed_bm25-FastEmbedBM25Embedder-model}

```python
model: str
```

The configured model name, or the FastEmbed default when unset.

##### `agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder.query_embed` \{#agrag-embedding-fastembed_bm25-FastEmbedBM25Embedder-query_embed}

```python
query_embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of search queries into BM25 sparse vectors.

Uses FastEmbed's `query_embed`, which assigns each unique query
term a uniform weight of `1.0` rather than the document-side
term-frequency and length-normalization weighting `embed` applies;
IDF weighting is applied separately by the sparse index's
`Modifier.IDF` at query time.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The query texts to embed, in order.

**Returns:**

- <code>list\[[SparseVector](#agrag-embedding-sparse_base-SparseVector)\]</code> – One sparse vector per input text, in the same order.

### `agrag.embedding.sentence_transformers` \{#agrag-embedding-sentence_transformers}

Sentence-transformers embedder implementation.

**Classes:**

- [**SentenceTransformerEmbedder**](#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder) – An embedder backed by sentence-transformers.

#### `agrag.embedding.sentence_transformers.SentenceTransformerEmbedder` \{#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder}

```python
SentenceTransformerEmbedder(*, settings:EmbeddingSettings | None = None, cache:EmbeddingCache | None = None, model:object | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Embedder](#agrag-embedding-base-Embedder)</code>

An embedder backed by sentence-transformers.

The model loads lazily on first `embed`, so constructing the embedder
does not touch the GPU or download weights. Every blocking call into the
model runs in a worker thread (`asyncio.to_thread`), so the event loop
stays free for other work while a large batch encodes.

**Functions:**

- [**dimensions**](#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-dimensions) – Return the dimension the loaded model produces.
- [**embed**](#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-embed) – Embed a batch of texts, using the cache where possible.
- [**embed_one**](#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-embed_one) – Embed a single text.

**Attributes:**

- [**distance**](#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-distance) (<code>[Distance](common.md#agrag-common-data_models-vector_record-Distance)</code>) – Return the distance metric for vector indexes created for this embedder.
- [**model**](#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-model) (<code>str</code>) – The configured model name.

**Parameters:**

- **settings** (<code>[EmbeddingSettings](#agrag-embedding-settings-EmbeddingSettings) | None</code>) – Embedder configuration. Defaults to `EmbeddingSettings()`.
- **cache** (<code>[EmbeddingCache](#agrag-embedding-base-EmbeddingCache) | None</code>) – An optional content-addressed cache. Defaults to a no-op cache.
- **model** (<code>object | None</code>) – A pre-built sentence-transformers model, for tests. When set,
  `__init__` imports nothing and `embed` calls this object
  directly instead of building one.
- **tracer** (<code>Tracer | None</code>) – Opens every span this embedder's methods produce.

##### `agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.dimensions` \{#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-dimensions}

```python
dimensions() -> int
```

Return the dimension the loaded model produces.

Calling this loads the model the first time, the same
lock-protected, worker-thread path `embed` uses, so it is safe to
call concurrently with `embed` without stalling the event loop or
loading a second copy of the model.

**Raises:**

- <code>[EmbeddingMissingExtraError](#agrag-embedding-errors-EmbeddingMissingExtraError)</code> – sentence-transformers is not installed.

##### `agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.distance` \{#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-distance}

```python
distance: Distance
```

Return the distance metric for vector indexes created for this embedder.

Defaults to cosine, which matches normalized sentence-transformer models.
Concrete embedders may override when their vectors use a different
metric.

##### `agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.embed` \{#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-embed}

```python
embed(texts:Sequence[str]) -> list[list[float]]
```

Embed a batch of texts, using the cache where possible.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The texts to embed, in order.

**Returns:**

- <code>list\[list\[float\]\]</code> – One vector per input text, in the same order.

##### `agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.embed_one` \{#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-embed_one}

```python
embed_one(text:str) -> list[float]
```

Embed a single text.

**Parameters:**

- **text** (<code>str</code>) – The text to embed.

**Returns:**

- <code>list\[float\]</code> – The text's embedding vector.

##### `agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.model` \{#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-model}

```python
model: str
```

The configured model name.

### `agrag.embedding.settings` \{#agrag-embedding-settings}

Settings for the sentence-transformers embedder.

**Classes:**

- [**EmbeddingSettings**](#agrag-embedding-settings-EmbeddingSettings) – Sentence-transformers embedder configuration.

#### `agrag.embedding.settings.EmbeddingSettings` \{#agrag-embedding-settings-EmbeddingSettings}

Bases: <code>BaseSettings</code>

Sentence-transformers embedder configuration.

All fields are overridable via environment variables with the
`EMBEDDING_` prefix.

**Attributes:**

- [**model**](#agrag-embedding-settings-EmbeddingSettings-model) (<code>str</code>) – The sentence-transformers model name or path. Env: `EMBEDDING_MODEL`.
- [**device**](#agrag-embedding-settings-EmbeddingSettings-device) (<code>str | None</code>) – The device to load the model on, such as `"cpu"` or `"cuda"`.
  `None` uses sentence-transformers' own default detection. Env:
  `EMBEDDING_DEVICE`.
- [**normalize**](#agrag-embedding-settings-EmbeddingSettings-normalize) (<code>bool</code>) – Whether to L2-normalize output vectors. Env: `EMBEDDING_NORMALIZE`.
- [**batch_size**](#agrag-embedding-settings-EmbeddingSettings-batch_size) (<code>int</code>) – The number of texts encoded per `model.encode` call. Env:
  `EMBEDDING_BATCH_SIZE`.
- [**cache_folder**](#agrag-embedding-settings-EmbeddingSettings-cache_folder) (<code>str | None</code>) – Where sentence-transformers caches downloaded models.
  `None` uses the library default. Env: `EMBEDDING_CACHE_FOLDER`.

##### `agrag.embedding.settings.EmbeddingSettings.batch_size` \{#agrag-embedding-settings-EmbeddingSettings-batch_size}

```python
batch_size: int = 32
```

##### `agrag.embedding.settings.EmbeddingSettings.cache_folder` \{#agrag-embedding-settings-EmbeddingSettings-cache_folder}

```python
cache_folder: str | None = None
```

##### `agrag.embedding.settings.EmbeddingSettings.device` \{#agrag-embedding-settings-EmbeddingSettings-device}

```python
device: str | None = None
```

##### `agrag.embedding.settings.EmbeddingSettings.model` \{#agrag-embedding-settings-EmbeddingSettings-model}

```python
model: str = 'ibm-granite/granite-embedding-small-english-r2'
```

##### `agrag.embedding.settings.EmbeddingSettings.model_config` \{#agrag-embedding-settings-EmbeddingSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='EMBEDDING_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

##### `agrag.embedding.settings.EmbeddingSettings.normalize` \{#agrag-embedding-settings-EmbeddingSettings-normalize}

```python
normalize: bool = True
```

### `agrag.embedding.sparse_base` \{#agrag-embedding-sparse_base}

Sparse lexical vectors and the sparse embedder protocol.

**Classes:**

- [**SparseEmbedder**](#agrag-embedding-sparse_base-SparseEmbedder) – A component that turns text into sparse lexical vectors, for hybrid search.
- [**SparseVector**](#agrag-embedding-sparse_base-SparseVector) – A sparse vector: nonzero indices and their values.

#### `agrag.embedding.sparse_base.SparseEmbedder` \{#agrag-embedding-sparse_base-SparseEmbedder}

Bases: <code>ABC</code>

A component that turns text into sparse lexical vectors, for hybrid search.

**Functions:**

- [**embed**](#agrag-embedding-sparse_base-SparseEmbedder-embed) – Embed a batch of documents into sparse vectors.
- [**query_embed**](#agrag-embedding-sparse_base-SparseEmbedder-query_embed) – Embed a batch of search queries into sparse vectors.

**Attributes:**

- [**model**](#agrag-embedding-sparse_base-SparseEmbedder-model) (<code>str</code>) –

##### `agrag.embedding.sparse_base.SparseEmbedder.embed` \{#agrag-embedding-sparse_base-SparseEmbedder-embed}

```python
embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of documents into sparse vectors.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The document texts to embed, in order.

**Returns:**

- <code>list\[[SparseVector](#agrag-embedding-sparse_base-SparseVector)\]</code> – One sparse vector per input text, in the same order.

##### `agrag.embedding.sparse_base.SparseEmbedder.model` \{#agrag-embedding-sparse_base-SparseEmbedder-model}

```python
model: str
```

##### `agrag.embedding.sparse_base.SparseEmbedder.query_embed` \{#agrag-embedding-sparse_base-SparseEmbedder-query_embed}

```python
query_embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of search queries into sparse vectors.

Query-side sparse embedding is not always the same computation as
document-side embedding: BM25, for example, applies term-frequency
and document-length normalization on the document side but only a
uniform per-term weight on the query side, since IDF weighting is
applied by the sparse index at query time instead. Implementations
with no such asymmetry may implement this identically to `embed`.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The query texts to embed, in order.

**Returns:**

- <code>list\[[SparseVector](#agrag-embedding-sparse_base-SparseVector)\]</code> – One sparse vector per input text, in the same order.

#### `agrag.embedding.sparse_base.SparseVector` \{#agrag-embedding-sparse_base-SparseVector}

Bases: <code>BaseModel</code>

A sparse vector: nonzero indices and their values.

**Attributes:**

- [**indices**](#agrag-embedding-sparse_base-SparseVector-indices) (<code>list\[int\]</code>) – The positions of nonzero entries.
- [**values**](#agrag-embedding-sparse_base-SparseVector-values) (<code>list\[float\]</code>) – The weight at each index, aligned with `indices`.

##### `agrag.embedding.sparse_base.SparseVector.indices` \{#agrag-embedding-sparse_base-SparseVector-indices}

```python
indices: list[int]
```

##### `agrag.embedding.sparse_base.SparseVector.values` \{#agrag-embedding-sparse_base-SparseVector-values}

```python
values: list[float]
```
