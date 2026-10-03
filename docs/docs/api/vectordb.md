---
title: agrag.vectordb
sidebar_position: 12
---

## `agrag.vectordb` \{#agrag-vectordb}

Vector storage backends and the build shortcut.

**Modules:**

- [**base**](#agrag-vectordb-base) – The VectorStore abstraction and its build shortcut.
- [**errors**](#agrag-vectordb-errors) – Errors that the vector-store layer raises.
- [**milvus**](#agrag-vectordb-milvus) – Milvus vector-store backend.
- [**pending**](#agrag-vectordb-pending) – Pending-record bookkeeping shared by the VectorStore adapters.
- [**qdrant**](#agrag-vectordb-qdrant) – Qdrant vector-store backend.
- [**settings**](#agrag-vectordb-settings) – Settings for vector-store backends.
- [**weaviate**](#agrag-vectordb-weaviate) – Weaviate vector-store backend.

**Classes:**

- [**CollectionDimensionMismatchError**](#agrag-vectordb-CollectionDimensionMismatchError) – A collection already exists with a different embedding dimension.
- [**MilvusSettings**](#agrag-vectordb-MilvusSettings) – Milvus connection configuration.
- [**MilvusVectorStore**](#agrag-vectordb-MilvusVectorStore) – A `VectorStore` backed by Milvus, including native hybrid search.
- [**QdrantSettings**](#agrag-vectordb-QdrantSettings) – Qdrant connection configuration.
- [**QdrantVectorStore**](#agrag-vectordb-QdrantVectorStore) – A `VectorStore` backed by Qdrant, including native hybrid search.
- [**VectorStore**](#agrag-vectordb-VectorStore) – A vector database backend: collection lifecycle, writes, and search.
- [**VectorStoreError**](#agrag-vectordb-VectorStoreError) – The base class for every vector-store error.
- [**VectorStoreMissingExtraError**](#agrag-vectordb-VectorStoreMissingExtraError) – A vector store exists, but its package extra is not installed.
- [**WeaviateSettings**](#agrag-vectordb-WeaviateSettings) – Weaviate connection configuration.
- [**WeaviateVectorStore**](#agrag-vectordb-WeaviateVectorStore) – A `VectorStore` backed by Weaviate, including native hybrid search.

**Functions:**

- [**build_vector_store**](#agrag-vectordb-build_vector_store) – Build a vector store from a backend name, or return one unchanged.

### `agrag.vectordb.CollectionDimensionMismatchError` \{#agrag-vectordb-CollectionDimensionMismatchError}

```python
CollectionDimensionMismatchError(*, expected:int, actual:int) -> None
```

Bases: <code>[VectorStoreError](#agrag-vectordb-errors-VectorStoreError)</code>

A collection already exists with a different embedding dimension.

**Attributes:**

- [**expected**](#agrag-vectordb-CollectionDimensionMismatchError-expected) – The dimension the collection was created with.
- [**actual**](#agrag-vectordb-CollectionDimensionMismatchError-actual) – The dimension the caller requested.

#### `agrag.vectordb.CollectionDimensionMismatchError.actual` \{#agrag-vectordb-CollectionDimensionMismatchError-actual}

```python
actual = actual
```

#### `agrag.vectordb.CollectionDimensionMismatchError.expected` \{#agrag-vectordb-CollectionDimensionMismatchError-expected}

```python
expected = expected
```

### `agrag.vectordb.MilvusSettings` \{#agrag-vectordb-MilvusSettings}

Bases: <code>BaseSettings</code>

Milvus connection configuration.

**Attributes:**

- [**uri**](#agrag-vectordb-MilvusSettings-uri) (<code>str</code>) – The Milvus endpoint URI. Env: `MILVUS_URI`.
- [**token**](#agrag-vectordb-MilvusSettings-token) (<code>str</code>) – The Milvus auth token. Empty string for an unauthenticated
  instance. Env: `MILVUS_TOKEN`.
- [**require_tls**](#agrag-vectordb-MilvusSettings-require_tls) (<code>bool</code>) – When `True`, reject a plaintext `uri` to a
  non-local host even with no `token` configured. Off by default
  since many deployments run an unauthenticated Milvus on a
  private network and rely on network segmentation rather than
  transport encryption. Env: `MILVUS_REQUIRE_TLS`.

**Raises:**

- <code>ValueError</code> – `uri` is plaintext (`http`), points at a non-local
  host, and either `token` is set or `require_tls` is
  `True`. Use `https` for a remote Milvus instance.

#### `agrag.vectordb.MilvusSettings.model_config` \{#agrag-vectordb-MilvusSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='MILVUS_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

#### `agrag.vectordb.MilvusSettings.require_tls` \{#agrag-vectordb-MilvusSettings-require_tls}

```python
require_tls: bool = False
```

#### `agrag.vectordb.MilvusSettings.token` \{#agrag-vectordb-MilvusSettings-token}

```python
token: str = ''
```

#### `agrag.vectordb.MilvusSettings.uri` \{#agrag-vectordb-MilvusSettings-uri}

```python
uri: str = 'http://localhost:19530'
```

### `agrag.vectordb.MilvusVectorStore` \{#agrag-vectordb-MilvusVectorStore}

```python
MilvusVectorStore(*, settings:MilvusSettings | None = None, client:Any | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[VectorStore](#agrag-vectordb-base-VectorStore)</code>

A `VectorStore` backed by Milvus, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Milvus performs BM25 server-side, so hybrid
search needs no client-side sparse embedder; the sparse vector is computed
by a Milvus `Function` from the `text` field on write and at query time.

**Functions:**

- [**close**](#agrag-vectordb-MilvusVectorStore-close) – Release the backend connection.
- [**collection_exists**](#agrag-vectordb-MilvusVectorStore-collection_exists) – Report whether a collection exists.
- [**commit_pending**](#agrag-vectordb-MilvusVectorStore-commit_pending) – Promote one job's staged records to committed records.
- [**count**](#agrag-vectordb-MilvusVectorStore-count) – Count records in a collection.
- [**delete**](#agrag-vectordb-MilvusVectorStore-delete) – Delete records by id.
- [**delete_collection**](#agrag-vectordb-MilvusVectorStore-delete_collection) – Delete a collection and all its entities.
- [**delete_pending**](#agrag-vectordb-MilvusVectorStore-delete_pending) – Delete one job's staged records, leaving committed records alone.
- [**ensure_collection**](#agrag-vectordb-MilvusVectorStore-ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag-vectordb-MilvusVectorStore-hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag-vectordb-MilvusVectorStore-initialize) – Check connectivity and authentication.
- [**invalidate_collection**](#agrag-vectordb-MilvusVectorStore-invalidate_collection) – Drop cached distance-metric knowledge of a collection.
- [**retrieve**](#agrag-vectordb-MilvusVectorStore-retrieve) – Fetch records by id.
- [**scroll**](#agrag-vectordb-MilvusVectorStore-scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag-vectordb-MilvusVectorStore-search) – Search by dense vector only.
- [**upsert**](#agrag-vectordb-MilvusVectorStore-upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[MilvusSettings](#agrag-vectordb-settings-MilvusSettings) | None</code>) – Milvus connection settings. Defaults to
  `MilvusSettings()`.
- **client** (<code>Any | None</code>) – A pre-built `AsyncMilvusClient`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.
- **tracer** (<code>Tracer | None</code>) – Opens this store's spans.

#### `agrag.vectordb.MilvusVectorStore.close` \{#agrag-vectordb-MilvusVectorStore-close}

```python
close() -> None
```

Release the backend connection.

#### `agrag.vectordb.MilvusVectorStore.collection_exists` \{#agrag-vectordb-MilvusVectorStore-collection_exists}

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

**Returns:**

- <code>bool</code> – `True` if the collection exists.

#### `agrag.vectordb.MilvusVectorStore.commit_pending` \{#agrag-vectordb-MilvusVectorStore-commit_pending}

```python
commit_pending(collection:str, *, job_id:UUID) -> None
```

Promote one job's staged records to committed records.

Each staged record is written under its real id, which replaces any
committed record with that id, and the staged copy is deleted.
Re-running after a failure finishes the remaining records.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The committed job whose records become visible.

#### `agrag.vectordb.MilvusVectorStore.count` \{#agrag-vectordb-MilvusVectorStore-count}

```python
count(collection:str, *, filters:dict[str, Any] | None = None, pending_job_id:UUID | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>str</code>) – The collection to count.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on scalar fields.
- **pending_job_id** (<code>UUID | None</code>) – Count only this job's staged records.

**Returns:**

- <code>int</code> – The number of matching records.

#### `agrag.vectordb.MilvusVectorStore.delete` \{#agrag-vectordb-MilvusVectorStore-delete}

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to delete from.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to delete.

#### `agrag.vectordb.MilvusVectorStore.delete_collection` \{#agrag-vectordb-MilvusVectorStore-delete_collection}

```python
delete_collection(name:str) -> None
```

Delete a collection and all its entities.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

#### `agrag.vectordb.MilvusVectorStore.delete_pending` \{#agrag-vectordb-MilvusVectorStore-delete_pending}

```python
delete_pending(collection:str, *, job_id:UUID) -> None
```

Delete one job's staged records, leaving committed records alone.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The rolled-back job whose records are deleted.

#### `agrag.vectordb.MilvusVectorStore.ensure_collection` \{#agrag-vectordb-MilvusVectorStore-ensure_collection}

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

Milvus performs BM25 server-side, so the sparse field and its `Function`
are always provisioned; the `hybrid` flag is accepted for interface
parity but is a no-op here. An existing collection must already carry
this same fixed schema, since `upsert` and `hybrid_search` always
read and write every field regardless of `hybrid`.

**Parameters:**

- **name** (<code>str</code>) – The collection name.
- **dimensions** (<code>int</code>) – The embedding dimension.
- **distance** (<code>[Distance](common.md#agrag-common-data_models-vector_record-Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>bool</code>) – Accepted for interface parity; ignored by Milvus.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag-vectordb-errors-CollectionDimensionMismatchError)</code> – The collection exists with a
  different dimension than `dimensions`.
- <code>[VectorStoreError](#agrag-vectordb-errors-VectorStoreError)</code> – The collection exists but is missing a field or
  index this adapter requires.

#### `agrag.vectordb.MilvusVectorStore.hybrid_search` \{#agrag-vectordb-MilvusVectorStore-hybrid_search}

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

Fusion uses Milvus's native weighted reranker, which normalizes each
request's scores before applying `alpha`.

**Parameters:**

- **collection** (<code>str</code>) – The collection to search.
- **query_vector** (<code>Sequence\[float\]</code>) – The dense query embedding.
- **query_text** (<code>str</code>) – The query text, matched by BM25.
- **limit** (<code>int</code>) – The maximum number of hits to return.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on scalar fields.
- **alpha** (<code>float</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword.

**Returns:**

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – The fused hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`, or `alpha` is outside `[0.0, 1.0]`.

#### `agrag.vectordb.MilvusVectorStore.initialize` \{#agrag-vectordb-MilvusVectorStore-initialize}

```python
initialize() -> None
```

Check connectivity and authentication.

#### `agrag.vectordb.MilvusVectorStore.invalidate_collection` \{#agrag-vectordb-MilvusVectorStore-invalidate_collection}

```python
invalidate_collection(name:str) -> None
```

Drop cached distance-metric knowledge of a collection.

This store caches a collection's distance metric after the first
call that resolves it, on the assumption that it alone (via
`ensure_collection`/`delete_collection`) owns the collection's
lifecycle for as long as this instance is in use. If something
outside this instance deletes and recreates a collection under the
same name with a different metric, call this first so the next call
re-resolves that collection's metric from the backend instead of
trusting the stale cache.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

#### `agrag.vectordb.MilvusVectorStore.retrieve` \{#agrag-vectordb-MilvusVectorStore-retrieve}

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

Requests at most `MAX_RESPONSE_LIMIT` ids per call, so a large
`ids` list cannot exceed Milvus's response-size ceiling in one
request the way sending every id at once would.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to fetch.

**Returns:**

- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – ids.

#### `agrag.vectordb.MilvusVectorStore.scroll` \{#agrag-vectordb-MilvusVectorStore-scroll}

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False, pending_job_id:UUID | None = None) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

Milvus rejects a query whose `offset + limit` exceeds
`MAX_RESPONSE_LIMIT`, so a numeric offset cannot page past that
many total records. Pages instead cursor on the `id` primary key:
each page filters on `id > page_offset` and orders by `id`
ascending, which needs no offset at all and so never hits that
window regardless of collection size. The explicit order is load
bearing: without it, an unordered query result could omit rows at or
below the next cursor, permanently skipping them on the next page.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **limit** (<code>int</code>) – The maximum number of records per page.
- **page_offset** (<code>str | None</code>) – The id cursor from a previous `scroll` call.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on scalar fields.
- **with_vectors** (<code>bool</code>) – Whether to return each record's vector.
- **pending_job_id** (<code>UUID | None</code>) – Read only this job's staged records.

**Returns:**

- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – The page of records and the next page cursor, or `None` at the
- <code>str | None</code> – end.

#### `agrag.vectordb.MilvusVectorStore.search` \{#agrag-vectordb-MilvusVectorStore-search}

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>str</code>) – The collection to search.
- **query_vector** (<code>Sequence\[float\]</code>) – The dense query embedding.
- **limit** (<code>int</code>) – The maximum number of hits to return.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on scalar fields.

**Returns:**

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`.

#### `agrag.vectordb.MilvusVectorStore.upsert` \{#agrag-vectordb-MilvusVectorStore-upsert}

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None) -> None
```

Write or overwrite records in a collection.

**Parameters:**

- **collection** (<code>str</code>) – The collection to write to.
- **records** (<code>Sequence\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>int</code>) – The number of records per backend write call. Must be
  positive.
- **pending_job_id** (<code>UUID | None</code>) – The in-flight job staging these records.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.

### `agrag.vectordb.QdrantSettings` \{#agrag-vectordb-QdrantSettings}

Bases: <code>BaseSettings</code>

Qdrant connection configuration.

**Attributes:**

- [**url**](#agrag-vectordb-QdrantSettings-url) (<code>str</code>) – The Qdrant endpoint URL. Env: `QDRANT_URL`.
- [**api_key**](#agrag-vectordb-QdrantSettings-api_key) (<code>str</code>) – The Qdrant API key. Env: `QDRANT_API_KEY`.
- [**require_tls**](#agrag-vectordb-QdrantSettings-require_tls) (<code>bool</code>) – When `True`, reject a plaintext `url` to a non-local
  host even with no `api_key` configured. Off by default since
  many deployments run an unauthenticated Qdrant on a private
  network and rely on network segmentation rather than transport
  encryption. Env: `QDRANT_REQUIRE_TLS`.

**Raises:**

- <code>ValueError</code> – `url` is plaintext (`http`), points at a non-local
  host, and either `api_key` is set or `require_tls` is
  `True`. Use `https` for a remote Qdrant instance.

#### `agrag.vectordb.QdrantSettings.api_key` \{#agrag-vectordb-QdrantSettings-api_key}

```python
api_key: str = ''
```

#### `agrag.vectordb.QdrantSettings.model_config` \{#agrag-vectordb-QdrantSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='QDRANT_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

#### `agrag.vectordb.QdrantSettings.require_tls` \{#agrag-vectordb-QdrantSettings-require_tls}

```python
require_tls: bool = False
```

#### `agrag.vectordb.QdrantSettings.url` \{#agrag-vectordb-QdrantSettings-url}

```python
url: str = 'http://localhost:6333'
```

### `agrag.vectordb.QdrantVectorStore` \{#agrag-vectordb-QdrantVectorStore}

```python
QdrantVectorStore(*, settings:QdrantSettings | None = None, sparse_embedder:SparseEmbedder | None = None, client:Any | None = None, models:Any | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[VectorStore](#agrag-vectordb-base-VectorStore)</code>

A `VectorStore` backed by Qdrant, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Hybrid search builds its sparse query with a
`SparseEmbedder` that defaults to FastEmbed BM25 and loads only when a
hybrid call first runs, not at construction.

**Functions:**

- [**close**](#agrag-vectordb-QdrantVectorStore-close) – Release the backend connection.
- [**collection_exists**](#agrag-vectordb-QdrantVectorStore-collection_exists) – Report whether a collection exists.
- [**commit_pending**](#agrag-vectordb-QdrantVectorStore-commit_pending) – Promote one job's staged records to committed records.
- [**count**](#agrag-vectordb-QdrantVectorStore-count) – Count records in a collection.
- [**delete**](#agrag-vectordb-QdrantVectorStore-delete) – Delete records by id.
- [**delete_collection**](#agrag-vectordb-QdrantVectorStore-delete_collection) – Delete a collection and all its points.
- [**delete_pending**](#agrag-vectordb-QdrantVectorStore-delete_pending) – Delete one job's staged records, leaving committed records alone.
- [**ensure_collection**](#agrag-vectordb-QdrantVectorStore-ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag-vectordb-QdrantVectorStore-hybrid_search) – Search by dense vector and keyword text, fused by a weighted blend.
- [**initialize**](#agrag-vectordb-QdrantVectorStore-initialize) – Check connectivity and authentication.
- [**invalidate_collection**](#agrag-vectordb-QdrantVectorStore-invalidate_collection) – Drop cached hybrid-state and distance-metric knowledge of a collection.
- [**retrieve**](#agrag-vectordb-QdrantVectorStore-retrieve) – Fetch records by id.
- [**scroll**](#agrag-vectordb-QdrantVectorStore-scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag-vectordb-QdrantVectorStore-search) – Search by dense vector only.
- [**upsert**](#agrag-vectordb-QdrantVectorStore-upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[QdrantSettings](#agrag-vectordb-settings-QdrantSettings) | None</code>) – Qdrant connection settings. Defaults to
  `QdrantSettings()`.
- **sparse_embedder** (<code>[SparseEmbedder](embedding.md#agrag-embedding-sparse_base-SparseEmbedder) | None</code>) – The sparse embedder hybrid search uses. Defaults to
  a lazily-built `FastEmbedBM25Embedder`.
- **client** (<code>Any | None</code>) – A pre-built `AsyncQdrantClient`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.
- **models** (<code>Any | None</code>) – The `qdrant_client.models` module, for tests. Pair with
  `client` so filter/payload helpers work without needing the
  real `qdrant_client` package installed at all.
- **tracer** (<code>Tracer | None</code>) – Opens this store's spans.

#### `agrag.vectordb.QdrantVectorStore.close` \{#agrag-vectordb-QdrantVectorStore-close}

```python
close() -> None
```

Release the backend connection.

#### `agrag.vectordb.QdrantVectorStore.collection_exists` \{#agrag-vectordb-QdrantVectorStore-collection_exists}

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

**Returns:**

- <code>bool</code> – `True` if the collection exists.

#### `agrag.vectordb.QdrantVectorStore.commit_pending` \{#agrag-vectordb-QdrantVectorStore-commit_pending}

```python
commit_pending(collection:str, *, job_id:UUID) -> None
```

Promote one job's staged records to committed records.

Each staged record is written under its real id, which replaces any
committed record with that id, and the staged copy is deleted.
Re-running after a failure finishes the remaining records.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The committed job whose records become visible.

#### `agrag.vectordb.QdrantVectorStore.count` \{#agrag-vectordb-QdrantVectorStore-count}

```python
count(collection:str, *, filters:dict[str, Any] | None = None, pending_job_id:UUID | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>str</code>) – The collection to count.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on payload fields.
- **pending_job_id** (<code>UUID | None</code>) – Count only this job's staged records.

**Returns:**

- <code>int</code> – The number of matching records.

#### `agrag.vectordb.QdrantVectorStore.delete` \{#agrag-vectordb-QdrantVectorStore-delete}

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to delete from.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to delete.

#### `agrag.vectordb.QdrantVectorStore.delete_collection` \{#agrag-vectordb-QdrantVectorStore-delete_collection}

```python
delete_collection(name:str) -> None
```

Delete a collection and all its points.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

#### `agrag.vectordb.QdrantVectorStore.delete_pending` \{#agrag-vectordb-QdrantVectorStore-delete_pending}

```python
delete_pending(collection:str, *, job_id:UUID) -> None
```

Delete one job's staged records, leaving committed records alone.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The rolled-back job whose records are deleted.

#### `agrag.vectordb.QdrantVectorStore.ensure_collection` \{#agrag-vectordb-QdrantVectorStore-ensure_collection}

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>str</code>) – The collection name.
- **dimensions** (<code>int</code>) – The embedding dimension.
- **distance** (<code>[Distance](common.md#agrag-common-data_models-vector_record-Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>bool</code>) – Whether to provision the named sparse vector hybrid search
  needs.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag-vectordb-errors-CollectionDimensionMismatchError)</code> – The collection exists with a
  different dimension than `dimensions`.
- <code>[VectorStoreError](#agrag-vectordb-errors-VectorStoreError)</code> – The collection exists without hybrid search
  support and `hybrid=True` was requested.

#### `agrag.vectordb.QdrantVectorStore.hybrid_search` \{#agrag-vectordb-QdrantVectorStore-hybrid_search}

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

- **collection** (<code>str</code>) – The collection to search.
- **query_vector** (<code>Sequence\[float\]</code>) – The dense query embedding.
- **query_text** (<code>str</code>) – The query text, matched by BM25.
- **limit** (<code>int</code>) – The maximum number of hits to return.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on payload fields.
- **alpha** (<code>float</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword.

**Returns:**

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – The blended hits, highest combined score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`, or `alpha` is outside `[0.0, 1.0]`.

#### `agrag.vectordb.QdrantVectorStore.initialize` \{#agrag-vectordb-QdrantVectorStore-initialize}

```python
initialize() -> None
```

Check connectivity and authentication.

#### `agrag.vectordb.QdrantVectorStore.invalidate_collection` \{#agrag-vectordb-QdrantVectorStore-invalidate_collection}

```python
invalidate_collection(name:str) -> None
```

Drop cached hybrid-state and distance-metric knowledge of a collection.

This store caches a collection's hybrid support and distance metric
after the first call that resolves them, on the assumption that it
alone (via `ensure_collection`/`delete_collection`) owns the
collection's lifecycle for as long as this instance is in use. If
something outside this instance deletes and recreates a collection
under the same name with different config, call this first so the
next call re-resolves that collection's state from the backend
instead of trusting the stale cache.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

#### `agrag.vectordb.QdrantVectorStore.retrieve` \{#agrag-vectordb-QdrantVectorStore-retrieve}

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to fetch.

**Returns:**

- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – ids.

#### `agrag.vectordb.QdrantVectorStore.scroll` \{#agrag-vectordb-QdrantVectorStore-scroll}

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False, pending_job_id:UUID | None = None) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **limit** (<code>int</code>) – The maximum number of records per page.
- **page_offset** (<code>str | None</code>) – The offset from a previous `scroll` call.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on payload fields.
- **with_vectors** (<code>bool</code>) – Whether to return each record's vector.
- **pending_job_id** (<code>UUID | None</code>) – Read only this job's staged records.

**Returns:**

- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – The page of records and the next page offset, or `None` at the
- <code>str | None</code> – end.

#### `agrag.vectordb.QdrantVectorStore.search` \{#agrag-vectordb-QdrantVectorStore-search}

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>str</code>) – The collection to search.
- **query_vector** (<code>Sequence\[float\]</code>) – The dense query embedding.
- **limit** (<code>int</code>) – The maximum number of hits to return.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`.

#### `agrag.vectordb.QdrantVectorStore.upsert` \{#agrag-vectordb-QdrantVectorStore-upsert}

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None) -> None
```

Write or overwrite records in a collection.

With `pending_job_id` the records are staged for that job.

When `collection` has sparse-vector support (created or previously
seen with `ensure_collection(..., hybrid=True)`), each record's
`payload["text"]` is also sparse-embedded and stored under the named
sparse vector, so `hybrid_search`'s keyword arm has real vectors to
match. A record with no `text` payload key gets an empty sparse
vector and only ever surfaces through the dense side of a hybrid
search.

**Parameters:**

- **collection** (<code>str</code>) – The collection to write to.
- **records** (<code>Sequence\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>int</code>) – The number of records per backend write call. Must be
  positive.
- **pending_job_id** (<code>UUID | None</code>) – The in-flight job staging these records.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.

### `agrag.vectordb.VectorStore` \{#agrag-vectordb-VectorStore}

Bases: <code>ABC</code>

A vector database backend: collection lifecycle, writes, and search.

**Functions:**

- [**close**](#agrag-vectordb-VectorStore-close) – Release the backend connection.
- [**collection_exists**](#agrag-vectordb-VectorStore-collection_exists) – Report whether a collection exists.
- [**commit_pending**](#agrag-vectordb-VectorStore-commit_pending) – Promote one job's staged records to committed records.
- [**count**](#agrag-vectordb-VectorStore-count) – Count records in a collection.
- [**delete**](#agrag-vectordb-VectorStore-delete) – Delete records by id.
- [**delete_collection**](#agrag-vectordb-VectorStore-delete_collection) – Delete a collection and all its points.
- [**delete_pending**](#agrag-vectordb-VectorStore-delete_pending) – Delete one job's staged records, leaving committed records alone.
- [**ensure_collection**](#agrag-vectordb-VectorStore-ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag-vectordb-VectorStore-hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag-vectordb-VectorStore-initialize) – Check connectivity and authentication.
- [**retrieve**](#agrag-vectordb-VectorStore-retrieve) – Fetch records by id.
- [**scroll**](#agrag-vectordb-VectorStore-scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag-vectordb-VectorStore-search) – Search by dense vector only.
- [**upsert**](#agrag-vectordb-VectorStore-upsert) – Write or overwrite records in a collection.

#### `agrag.vectordb.VectorStore.close` \{#agrag-vectordb-VectorStore-close}

```python
close() -> None
```

Release the backend connection.

#### `agrag.vectordb.VectorStore.collection_exists` \{#agrag-vectordb-VectorStore-collection_exists}

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

**Returns:**

- <code>bool</code> – `True` if the collection exists.

#### `agrag.vectordb.VectorStore.commit_pending` \{#agrag-vectordb-VectorStore-commit_pending}

```python
commit_pending(collection:str, *, job_id:UUID) -> None
```

Promote one job's staged records to committed records.

Each staged record is written under its real id, which replaces any
committed record with that id, and the staged copy is deleted.
Re-running after a failure finishes the remaining records.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The committed job whose records become visible.

#### `agrag.vectordb.VectorStore.count` \{#agrag-vectordb-VectorStore-count}

```python
count(collection:str, *, filters:dict[str, Any] | None = None, pending_job_id:UUID | None = None) -> int
```

Count records in a collection.

Counts committed records only, unless `pending_job_id` names a job.

**Parameters:**

- **collection** (<code>str</code>) – The collection to count.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
  Keys must be valid identifiers (letters, digits, underscore,
  not starting with a digit) to stay portable: Milvus compiles
  them into a filter expression and Neo4j's `GraphStore`
  counterpart compiles them into Cypher, so both reject other
  characters, while Qdrant and Weaviate accept arbitrary payload
  keys.
- **pending_job_id** (<code>UUID | None</code>) – Count only that job's staged records instead of
  the committed ones.

**Returns:**

- <code>int</code> – The number of matching records.

#### `agrag.vectordb.VectorStore.delete` \{#agrag-vectordb-VectorStore-delete}

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to delete from.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to delete.

#### `agrag.vectordb.VectorStore.delete_collection` \{#agrag-vectordb-VectorStore-delete_collection}

```python
delete_collection(name:str) -> None
```

Delete a collection and all its points.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

#### `agrag.vectordb.VectorStore.delete_pending` \{#agrag-vectordb-VectorStore-delete_pending}

```python
delete_pending(collection:str, *, job_id:UUID) -> None
```

Delete one job's staged records, leaving committed records alone.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The rolled-back job whose records are deleted.

#### `agrag.vectordb.VectorStore.ensure_collection` \{#agrag-vectordb-VectorStore-ensure_collection}

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>str</code>) – The collection name.
- **dimensions** (<code>int</code>) – The embedding dimension. If the collection already
  exists with a different dimension, this raises.
- **distance** (<code>[Distance](common.md#agrag-common-data_models-vector_record-Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>bool</code>) – Whether to additionally provision the sparse-vector
  configuration hybrid search needs. Ignored by backends that
  need no such provisioning.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag-vectordb-errors-CollectionDimensionMismatchError)</code> – The collection exists with a
  different dimension than `dimensions`.

#### `agrag.vectordb.VectorStore.hybrid_search` \{#agrag-vectordb-VectorStore-hybrid_search}

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

Searches committed records only; staged records stay hidden.

**Parameters:**

- **collection** (<code>str</code>) – The collection to search. Must have been created with
  `ensure_collection(..., hybrid=True)`.
- **query_vector** (<code>Sequence\[float\]</code>) – The dense query embedding.
- **query_text** (<code>str</code>) – The query text, matched by keyword/BM25.
- **limit** (<code>int</code>) – The maximum number of hits to return.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
  Keys must be valid identifiers (letters, digits, underscore,
  not starting with a digit) to stay portable: Milvus compiles
  them into a filter expression and Neo4j's `GraphStore`
  counterpart compiles them into Cypher, so both reject other
  characters, while Qdrant and Weaviate accept arbitrary payload
  keys.
- **alpha** (<code>float</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword. Weaviate and Milvus apply this weight natively.
  Qdrant's native fusion (Reciprocal Rank Fusion) has no
  continuous weight, so it applies `alpha` by blending two
  independently-scored, min-max normalized result sets instead
  of a single native fused call.

**Returns:**

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – The fused hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `agrag.common.validation.MAX_SEARCH_LIMIT`, or `alpha` is
  outside `[0.0, 1.0]`. Enforced uniformly across backends
  since they otherwise fail differently outside that range.

#### `agrag.vectordb.VectorStore.initialize` \{#agrag-vectordb-VectorStore-initialize}

```python
initialize() -> None
```

Check connectivity and authentication.

**Raises:**

- <code>[VectorStoreError](#agrag-vectordb-errors-VectorStoreError)</code> – The backend is unreachable, or the credentials
  are rejected.

#### `agrag.vectordb.VectorStore.retrieve` \{#agrag-vectordb-VectorStore-retrieve}

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to fetch.

**Returns:**

- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – ids.

#### `agrag.vectordb.VectorStore.scroll` \{#agrag-vectordb-VectorStore-scroll}

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False, pending_job_id:UUID | None = None) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

Reads committed records only, unless `pending_job_id` names a job.
Do not write or delete records of the set being read between pages:
a backend may page by position.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **limit** (<code>int</code>) – The maximum number of records per page.
- **page_offset** (<code>str | None</code>) – The offset from a previous `scroll` call, or
  `None` to start at the beginning.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
  Keys must be valid identifiers (letters, digits, underscore,
  not starting with a digit) to stay portable: Milvus compiles
  them into a filter expression and Neo4j's `GraphStore`
  counterpart compiles them into Cypher, so both reject other
  characters, while Qdrant and Weaviate accept arbitrary payload
  keys.
- **with_vectors** (<code>bool</code>) – Whether to return each record's vector.
- **pending_job_id** (<code>UUID | None</code>) – Read only that job's staged records instead of
  the committed ones.

**Returns:**

- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – The page of records and the next page offset, or `None` at the
- <code>str | None</code> – end.

#### `agrag.vectordb.VectorStore.search` \{#agrag-vectordb-VectorStore-search}

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

Searches committed records only; staged records stay hidden.

**Parameters:**

- **collection** (<code>str</code>) – The collection to search.
- **query_vector** (<code>Sequence\[float\]</code>) – The dense query embedding.
- **limit** (<code>int</code>) – The maximum number of hits to return.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
  Keys must be valid identifiers (letters, digits, underscore,
  not starting with a digit) to stay portable: Milvus compiles
  them into a filter expression and Neo4j's `GraphStore`
  counterpart compiles them into Cypher, so both reject other
  characters, while Qdrant and Weaviate accept arbitrary payload
  keys.

**Returns:**

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `agrag.common.validation.MAX_SEARCH_LIMIT`. Enforced
  uniformly across backends since they otherwise fail
  differently outside that range.

#### `agrag.vectordb.VectorStore.upsert` \{#agrag-vectordb-VectorStore-upsert}

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None) -> None
```

Write or overwrite records in a collection.

**Parameters:**

- **collection** (<code>str</code>) – The collection to write to.
- **records** (<code>Sequence\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>int</code>) – The number of records per backend write call. Must be
  positive.
- **pending_job_id** (<code>UUID | None</code>) – The in-flight Cutover Job writing these records.
  The store keeps them under staging ids, hidden from search,
  scroll and count until :meth:`commit_pending` promotes them,
  so a committed record with the same id stays searchable and
  survives :meth:`delete_pending`. None writes committed
  records.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.

### `agrag.vectordb.VectorStoreError` \{#agrag-vectordb-VectorStoreError}

Bases: <code>Exception</code>

The base class for every vector-store error.

### `agrag.vectordb.VectorStoreMissingExtraError` \{#agrag-vectordb-VectorStoreMissingExtraError}

```python
VectorStoreMissingExtraError(extra:str) -> None
```

Bases: <code>[VectorStoreError](#agrag-vectordb-errors-VectorStoreError)</code>

A vector store exists, but its package extra is not installed.

**Attributes:**

- [**extra**](#agrag-vectordb-VectorStoreMissingExtraError-extra) – The name of the package extra to install.

#### `agrag.vectordb.VectorStoreMissingExtraError.extra` \{#agrag-vectordb-VectorStoreMissingExtraError-extra}

```python
extra = extra
```

### `agrag.vectordb.WeaviateSettings` \{#agrag-vectordb-WeaviateSettings}

Bases: <code>BaseSettings</code>

Weaviate connection configuration.

**Attributes:**

- [**mode**](#agrag-vectordb-WeaviateSettings-mode) (<code>Literal['cloud', 'custom']</code>) – `"cloud"` connects to Weaviate Cloud. `"custom"` connects to
  a self-hosted instance (used by integration tests against the local
  Docker Compose instance) — an explicit field, not inferred from the
  URL, since inference caused real connection bugs in surveyed
  reference implementations. Env: `WEAVIATE_MODE`.
- [**url**](#agrag-vectordb-WeaviateSettings-url) (<code>str</code>) – The Weaviate endpoint URL. For `"cloud"`, the cluster URL. For
  `"custom"`, the full host URL. Env: `WEAVIATE_URL`.
- [**api_key**](#agrag-vectordb-WeaviateSettings-api_key) (<code>str</code>) – The Weaviate API key. Env: `WEAVIATE_API_KEY`.
- [**grpc_port**](#agrag-vectordb-WeaviateSettings-grpc_port) (<code>int</code>) – The gRPC port, used by `"custom"` mode only (`"cloud"`
  mode infers it). Env: `WEAVIATE_GRPC_PORT`.
- [**require_tls**](#agrag-vectordb-WeaviateSettings-require_tls) (<code>bool</code>) – When `True`, reject a plaintext `url` to a non-local
  host even with no `api_key` configured. Off by default since
  many deployments run an unauthenticated Weaviate on a private
  network and rely on network segmentation rather than transport
  encryption. Env: `WEAVIATE_REQUIRE_TLS`.

**Raises:**

- <code>ValueError</code> – `url` is plaintext (`http`), points at a non-local
  host, and either `api_key` is set or `require_tls` is
  `True`. Use `https` for a remote Weaviate instance.

#### `agrag.vectordb.WeaviateSettings.api_key` \{#agrag-vectordb-WeaviateSettings-api_key}

```python
api_key: str = ''
```

#### `agrag.vectordb.WeaviateSettings.grpc_port` \{#agrag-vectordb-WeaviateSettings-grpc_port}

```python
grpc_port: int = 50051
```

#### `agrag.vectordb.WeaviateSettings.mode` \{#agrag-vectordb-WeaviateSettings-mode}

```python
mode: Literal['cloud', 'custom'] = 'custom'
```

#### `agrag.vectordb.WeaviateSettings.model_config` \{#agrag-vectordb-WeaviateSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='WEAVIATE_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

#### `agrag.vectordb.WeaviateSettings.require_tls` \{#agrag-vectordb-WeaviateSettings-require_tls}

```python
require_tls: bool = False
```

#### `agrag.vectordb.WeaviateSettings.url` \{#agrag-vectordb-WeaviateSettings-url}

```python
url: str = 'http://localhost:8080'
```

### `agrag.vectordb.WeaviateVectorStore` \{#agrag-vectordb-WeaviateVectorStore}

```python
WeaviateVectorStore(*, settings:WeaviateSettings | None = None, client:Any | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[VectorStore](#agrag-vectordb-base-VectorStore)</code>

A `VectorStore` backed by Weaviate, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Weaviate does its own server-side BM25, so
hybrid search needs no client-side sparse embedder.

**Functions:**

- [**close**](#agrag-vectordb-WeaviateVectorStore-close) – Release the backend connection.
- [**collection_exists**](#agrag-vectordb-WeaviateVectorStore-collection_exists) – Report whether a collection exists.
- [**commit_pending**](#agrag-vectordb-WeaviateVectorStore-commit_pending) – Promote one job's staged records to committed records.
- [**count**](#agrag-vectordb-WeaviateVectorStore-count) – Count records in a collection.
- [**delete**](#agrag-vectordb-WeaviateVectorStore-delete) – Delete records by id.
- [**delete_collection**](#agrag-vectordb-WeaviateVectorStore-delete_collection) – Delete a collection and all its objects.
- [**delete_pending**](#agrag-vectordb-WeaviateVectorStore-delete_pending) – Delete one job's staged records, leaving committed records alone.
- [**ensure_collection**](#agrag-vectordb-WeaviateVectorStore-ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag-vectordb-WeaviateVectorStore-hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag-vectordb-WeaviateVectorStore-initialize) – Open the connection and check authentication.
- [**retrieve**](#agrag-vectordb-WeaviateVectorStore-retrieve) – Fetch records by id.
- [**scroll**](#agrag-vectordb-WeaviateVectorStore-scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag-vectordb-WeaviateVectorStore-search) – Search by dense vector only.
- [**upsert**](#agrag-vectordb-WeaviateVectorStore-upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[WeaviateSettings](#agrag-vectordb-settings-WeaviateSettings) | None</code>) – Weaviate connection settings. Defaults to
  `WeaviateSettings()`.
- **client** (<code>Any | None</code>) – A pre-built Weaviate async client, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.
- **tracer** (<code>Tracer | None</code>) – Opens this store's spans.

#### `agrag.vectordb.WeaviateVectorStore.close` \{#agrag-vectordb-WeaviateVectorStore-close}

```python
close() -> None
```

Release the backend connection.

#### `agrag.vectordb.WeaviateVectorStore.collection_exists` \{#agrag-vectordb-WeaviateVectorStore-collection_exists}

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

**Returns:**

- <code>bool</code> – `True` if the collection exists.

#### `agrag.vectordb.WeaviateVectorStore.commit_pending` \{#agrag-vectordb-WeaviateVectorStore-commit_pending}

```python
commit_pending(collection:str, *, job_id:UUID) -> None
```

Promote one job's staged records to committed records.

Each staged record is written under its real id, which replaces any
committed record with that id, and the staged copy is deleted.
Re-running after a failure finishes the remaining records.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The committed job whose records become visible.

#### `agrag.vectordb.WeaviateVectorStore.count` \{#agrag-vectordb-WeaviateVectorStore-count}

```python
count(collection:str, *, filters:dict[str, Any] | None = None, pending_job_id:UUID | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>str</code>) – The collection to count.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on payload fields.
- **pending_job_id** (<code>UUID | None</code>) – Count only this job's staged records.

**Returns:**

- <code>int</code> – The number of matching records.

#### `agrag.vectordb.WeaviateVectorStore.delete` \{#agrag-vectordb-WeaviateVectorStore-delete}

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to delete from.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to delete.

#### `agrag.vectordb.WeaviateVectorStore.delete_collection` \{#agrag-vectordb-WeaviateVectorStore-delete_collection}

```python
delete_collection(name:str) -> None
```

Delete a collection and all its objects.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

#### `agrag.vectordb.WeaviateVectorStore.delete_pending` \{#agrag-vectordb-WeaviateVectorStore-delete_pending}

```python
delete_pending(collection:str, *, job_id:UUID) -> None
```

Delete one job's staged records, leaving committed records alone.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The rolled-back job whose records are deleted.

#### `agrag.vectordb.WeaviateVectorStore.ensure_collection` \{#agrag-vectordb-WeaviateVectorStore-ensure_collection}

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>str</code>) – The collection name.
- **dimensions** (<code>int</code>) – The embedding dimension.
- **distance** (<code>[Distance](common.md#agrag-common-data_models-vector_record-Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>bool</code>) – No-op for Weaviate, which needs no sparse provisioning.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag-vectordb-errors-CollectionDimensionMismatchError)</code> – An existing object in the
  collection carries a vector of a different dimension. Weaviate
  keeps no schema-level dimension for self-provided vectors, so
  an existing collection with no vector-bearing object cannot be
  checked this way.

#### `agrag.vectordb.WeaviateVectorStore.hybrid_search` \{#agrag-vectordb-WeaviateVectorStore-hybrid_search}

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

**Parameters:**

- **collection** (<code>str</code>) – The collection to search.
- **query_vector** (<code>Sequence\[float\]</code>) – The dense query embedding.
- **query_text** (<code>str</code>) – The query text, matched by keyword/BM25.
- **limit** (<code>int</code>) – The maximum number of hits to return.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on payload fields.
- **alpha** (<code>float</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword.

**Returns:**

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – The fused hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`, or `alpha` is outside `[0.0, 1.0]`.

#### `agrag.vectordb.WeaviateVectorStore.initialize` \{#agrag-vectordb-WeaviateVectorStore-initialize}

```python
initialize() -> None
```

Open the connection and check authentication.

#### `agrag.vectordb.WeaviateVectorStore.retrieve` \{#agrag-vectordb-WeaviateVectorStore-retrieve}

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to fetch.

**Returns:**

- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – ids.

#### `agrag.vectordb.WeaviateVectorStore.scroll` \{#agrag-vectordb-WeaviateVectorStore-scroll}

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False, pending_job_id:UUID | None = None) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

Weaviate rejects a cursor (`after`) combined with a filter, and
every read here carries the pending filter, so pages use a numeric
offset. Weaviate caps `offset + limit` at its
`QUERY_MAXIMUM_RESULTS` setting, 10000 by default.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **limit** (<code>int</code>) – The maximum number of records per page.
- **page_offset** (<code>str | None</code>) – The offset from a previous `scroll` call.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on payload fields.
- **with_vectors** (<code>bool</code>) – Whether to return each record's vector.
- **pending_job_id** (<code>UUID | None</code>) – Read only this job's staged records.

**Returns:**

- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – The page of records and the next page offset, or `None` at the
- <code>str | None</code> – end.

#### `agrag.vectordb.WeaviateVectorStore.search` \{#agrag-vectordb-WeaviateVectorStore-search}

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>str</code>) – The collection to search.
- **query_vector** (<code>Sequence\[float\]</code>) – The dense query embedding.
- **limit** (<code>int</code>) – The maximum number of hits to return.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`.

#### `agrag.vectordb.WeaviateVectorStore.upsert` \{#agrag-vectordb-WeaviateVectorStore-upsert}

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None) -> None
```

Write or overwrite records in a collection.

Uses Weaviate's batch import, which replaces an existing object
sharing a written id instead of rejecting it, giving real
insert-or-replace semantics and per-call batching in one request.

**Parameters:**

- **collection** (<code>str</code>) – The collection to write to.
- **records** (<code>Sequence\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>int</code>) – The number of records per backend write call. Must be
  positive.
- **pending_job_id** (<code>UUID | None</code>) – The in-flight job staging these records.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.
- <code>[VectorStoreError](#agrag-vectordb-errors-VectorStoreError)</code> – At least one record in a batch failed to write.

### `agrag.vectordb.base` \{#agrag-vectordb-base}

The VectorStore abstraction and its build shortcut.

**Classes:**

- [**VectorStore**](#agrag-vectordb-base-VectorStore) – A vector database backend: collection lifecycle, writes, and search.

#### `agrag.vectordb.base.VectorStore` \{#agrag-vectordb-base-VectorStore}

Bases: <code>ABC</code>

A vector database backend: collection lifecycle, writes, and search.

**Functions:**

- [**close**](#agrag-vectordb-base-VectorStore-close) – Release the backend connection.
- [**collection_exists**](#agrag-vectordb-base-VectorStore-collection_exists) – Report whether a collection exists.
- [**commit_pending**](#agrag-vectordb-base-VectorStore-commit_pending) – Promote one job's staged records to committed records.
- [**count**](#agrag-vectordb-base-VectorStore-count) – Count records in a collection.
- [**delete**](#agrag-vectordb-base-VectorStore-delete) – Delete records by id.
- [**delete_collection**](#agrag-vectordb-base-VectorStore-delete_collection) – Delete a collection and all its points.
- [**delete_pending**](#agrag-vectordb-base-VectorStore-delete_pending) – Delete one job's staged records, leaving committed records alone.
- [**ensure_collection**](#agrag-vectordb-base-VectorStore-ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag-vectordb-base-VectorStore-hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag-vectordb-base-VectorStore-initialize) – Check connectivity and authentication.
- [**retrieve**](#agrag-vectordb-base-VectorStore-retrieve) – Fetch records by id.
- [**scroll**](#agrag-vectordb-base-VectorStore-scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag-vectordb-base-VectorStore-search) – Search by dense vector only.
- [**upsert**](#agrag-vectordb-base-VectorStore-upsert) – Write or overwrite records in a collection.

##### `agrag.vectordb.base.VectorStore.close` \{#agrag-vectordb-base-VectorStore-close}

```python
close() -> None
```

Release the backend connection.

##### `agrag.vectordb.base.VectorStore.collection_exists` \{#agrag-vectordb-base-VectorStore-collection_exists}

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

**Returns:**

- <code>bool</code> – `True` if the collection exists.

##### `agrag.vectordb.base.VectorStore.commit_pending` \{#agrag-vectordb-base-VectorStore-commit_pending}

```python
commit_pending(collection:str, *, job_id:UUID) -> None
```

Promote one job's staged records to committed records.

Each staged record is written under its real id, which replaces any
committed record with that id, and the staged copy is deleted.
Re-running after a failure finishes the remaining records.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The committed job whose records become visible.

##### `agrag.vectordb.base.VectorStore.count` \{#agrag-vectordb-base-VectorStore-count}

```python
count(collection:str, *, filters:dict[str, Any] | None = None, pending_job_id:UUID | None = None) -> int
```

Count records in a collection.

Counts committed records only, unless `pending_job_id` names a job.

**Parameters:**

- **collection** (<code>str</code>) – The collection to count.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
  Keys must be valid identifiers (letters, digits, underscore,
  not starting with a digit) to stay portable: Milvus compiles
  them into a filter expression and Neo4j's `GraphStore`
  counterpart compiles them into Cypher, so both reject other
  characters, while Qdrant and Weaviate accept arbitrary payload
  keys.
- **pending_job_id** (<code>UUID | None</code>) – Count only that job's staged records instead of
  the committed ones.

**Returns:**

- <code>int</code> – The number of matching records.

##### `agrag.vectordb.base.VectorStore.delete` \{#agrag-vectordb-base-VectorStore-delete}

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to delete from.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to delete.

##### `agrag.vectordb.base.VectorStore.delete_collection` \{#agrag-vectordb-base-VectorStore-delete_collection}

```python
delete_collection(name:str) -> None
```

Delete a collection and all its points.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

##### `agrag.vectordb.base.VectorStore.delete_pending` \{#agrag-vectordb-base-VectorStore-delete_pending}

```python
delete_pending(collection:str, *, job_id:UUID) -> None
```

Delete one job's staged records, leaving committed records alone.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The rolled-back job whose records are deleted.

##### `agrag.vectordb.base.VectorStore.ensure_collection` \{#agrag-vectordb-base-VectorStore-ensure_collection}

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>str</code>) – The collection name.
- **dimensions** (<code>int</code>) – The embedding dimension. If the collection already
  exists with a different dimension, this raises.
- **distance** (<code>[Distance](common.md#agrag-common-data_models-vector_record-Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>bool</code>) – Whether to additionally provision the sparse-vector
  configuration hybrid search needs. Ignored by backends that
  need no such provisioning.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag-vectordb-errors-CollectionDimensionMismatchError)</code> – The collection exists with a
  different dimension than `dimensions`.

##### `agrag.vectordb.base.VectorStore.hybrid_search` \{#agrag-vectordb-base-VectorStore-hybrid_search}

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

Searches committed records only; staged records stay hidden.

**Parameters:**

- **collection** (<code>str</code>) – The collection to search. Must have been created with
  `ensure_collection(..., hybrid=True)`.
- **query_vector** (<code>Sequence\[float\]</code>) – The dense query embedding.
- **query_text** (<code>str</code>) – The query text, matched by keyword/BM25.
- **limit** (<code>int</code>) – The maximum number of hits to return.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
  Keys must be valid identifiers (letters, digits, underscore,
  not starting with a digit) to stay portable: Milvus compiles
  them into a filter expression and Neo4j's `GraphStore`
  counterpart compiles them into Cypher, so both reject other
  characters, while Qdrant and Weaviate accept arbitrary payload
  keys.
- **alpha** (<code>float</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword. Weaviate and Milvus apply this weight natively.
  Qdrant's native fusion (Reciprocal Rank Fusion) has no
  continuous weight, so it applies `alpha` by blending two
  independently-scored, min-max normalized result sets instead
  of a single native fused call.

**Returns:**

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – The fused hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `agrag.common.validation.MAX_SEARCH_LIMIT`, or `alpha` is
  outside `[0.0, 1.0]`. Enforced uniformly across backends
  since they otherwise fail differently outside that range.

##### `agrag.vectordb.base.VectorStore.initialize` \{#agrag-vectordb-base-VectorStore-initialize}

```python
initialize() -> None
```

Check connectivity and authentication.

**Raises:**

- <code>[VectorStoreError](#agrag-vectordb-errors-VectorStoreError)</code> – The backend is unreachable, or the credentials
  are rejected.

##### `agrag.vectordb.base.VectorStore.retrieve` \{#agrag-vectordb-base-VectorStore-retrieve}

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to fetch.

**Returns:**

- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – ids.

##### `agrag.vectordb.base.VectorStore.scroll` \{#agrag-vectordb-base-VectorStore-scroll}

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False, pending_job_id:UUID | None = None) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

Reads committed records only, unless `pending_job_id` names a job.
Do not write or delete records of the set being read between pages:
a backend may page by position.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **limit** (<code>int</code>) – The maximum number of records per page.
- **page_offset** (<code>str | None</code>) – The offset from a previous `scroll` call, or
  `None` to start at the beginning.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
  Keys must be valid identifiers (letters, digits, underscore,
  not starting with a digit) to stay portable: Milvus compiles
  them into a filter expression and Neo4j's `GraphStore`
  counterpart compiles them into Cypher, so both reject other
  characters, while Qdrant and Weaviate accept arbitrary payload
  keys.
- **with_vectors** (<code>bool</code>) – Whether to return each record's vector.
- **pending_job_id** (<code>UUID | None</code>) – Read only that job's staged records instead of
  the committed ones.

**Returns:**

- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – The page of records and the next page offset, or `None` at the
- <code>str | None</code> – end.

##### `agrag.vectordb.base.VectorStore.search` \{#agrag-vectordb-base-VectorStore-search}

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

Searches committed records only; staged records stay hidden.

**Parameters:**

- **collection** (<code>str</code>) – The collection to search.
- **query_vector** (<code>Sequence\[float\]</code>) – The dense query embedding.
- **limit** (<code>int</code>) – The maximum number of hits to return.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
  Keys must be valid identifiers (letters, digits, underscore,
  not starting with a digit) to stay portable: Milvus compiles
  them into a filter expression and Neo4j's `GraphStore`
  counterpart compiles them into Cypher, so both reject other
  characters, while Qdrant and Weaviate accept arbitrary payload
  keys.

**Returns:**

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `agrag.common.validation.MAX_SEARCH_LIMIT`. Enforced
  uniformly across backends since they otherwise fail
  differently outside that range.

##### `agrag.vectordb.base.VectorStore.upsert` \{#agrag-vectordb-base-VectorStore-upsert}

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None) -> None
```

Write or overwrite records in a collection.

**Parameters:**

- **collection** (<code>str</code>) – The collection to write to.
- **records** (<code>Sequence\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>int</code>) – The number of records per backend write call. Must be
  positive.
- **pending_job_id** (<code>UUID | None</code>) – The in-flight Cutover Job writing these records.
  The store keeps them under staging ids, hidden from search,
  scroll and count until :meth:`commit_pending` promotes them,
  so a committed record with the same id stays searchable and
  survives :meth:`delete_pending`. None writes committed
  records.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.

### `agrag.vectordb.build_vector_store` \{#agrag-vectordb-build_vector_store}

```python
build_vector_store(value:VectorStoreName | VectorStore, *, tracer:Tracer | None = None) -> VectorStore
```

Build a vector store from a backend name, or return one unchanged.

**Parameters:**

- **value** (<code>VectorStoreName | [VectorStore](#agrag-vectordb-base-VectorStore)</code>) – `"qdrant"` or `"weaviate"`, or an already-constructed
  `VectorStore` for full control over settings.
- **tracer** (<code>Tracer | None</code>) – Passed to the newly-built store. Not valid together with an
  already-constructed `value` -- that instance's tracer, if any,
  was already fixed at its own construction.

**Returns:**

- <code>[VectorStore](#agrag-vectordb-base-VectorStore)</code> – A ready-to-use vector store.

**Raises:**

- <code>ValueError</code> – `tracer` is given together with an already-constructed
  `value`.

### `agrag.vectordb.errors` \{#agrag-vectordb-errors}

Errors that the vector-store layer raises.

**Classes:**

- [**CollectionDimensionMismatchError**](#agrag-vectordb-errors-CollectionDimensionMismatchError) – A collection already exists with a different embedding dimension.
- [**VectorStoreError**](#agrag-vectordb-errors-VectorStoreError) – The base class for every vector-store error.
- [**VectorStoreMissingExtraError**](#agrag-vectordb-errors-VectorStoreMissingExtraError) – A vector store exists, but its package extra is not installed.

#### `agrag.vectordb.errors.CollectionDimensionMismatchError` \{#agrag-vectordb-errors-CollectionDimensionMismatchError}

```python
CollectionDimensionMismatchError(*, expected:int, actual:int) -> None
```

Bases: <code>[VectorStoreError](#agrag-vectordb-errors-VectorStoreError)</code>

A collection already exists with a different embedding dimension.

**Attributes:**

- [**expected**](#agrag-vectordb-errors-CollectionDimensionMismatchError-expected) – The dimension the collection was created with.
- [**actual**](#agrag-vectordb-errors-CollectionDimensionMismatchError-actual) – The dimension the caller requested.

##### `agrag.vectordb.errors.CollectionDimensionMismatchError.actual` \{#agrag-vectordb-errors-CollectionDimensionMismatchError-actual}

```python
actual = actual
```

##### `agrag.vectordb.errors.CollectionDimensionMismatchError.expected` \{#agrag-vectordb-errors-CollectionDimensionMismatchError-expected}

```python
expected = expected
```

#### `agrag.vectordb.errors.VectorStoreError` \{#agrag-vectordb-errors-VectorStoreError}

Bases: <code>Exception</code>

The base class for every vector-store error.

#### `agrag.vectordb.errors.VectorStoreMissingExtraError` \{#agrag-vectordb-errors-VectorStoreMissingExtraError}

```python
VectorStoreMissingExtraError(extra:str) -> None
```

Bases: <code>[VectorStoreError](#agrag-vectordb-errors-VectorStoreError)</code>

A vector store exists, but its package extra is not installed.

**Attributes:**

- [**extra**](#agrag-vectordb-errors-VectorStoreMissingExtraError-extra) – The name of the package extra to install.

##### `agrag.vectordb.errors.VectorStoreMissingExtraError.extra` \{#agrag-vectordb-errors-VectorStoreMissingExtraError-extra}

```python
extra = extra
```

### `agrag.vectordb.milvus` \{#agrag-vectordb-milvus}

Milvus vector-store backend.

**Classes:**

- [**MilvusVectorStore**](#agrag-vectordb-milvus-MilvusVectorStore) – A `VectorStore` backed by Milvus, including native hybrid search.

**Attributes:**

- [**MAX_RESPONSE_LIMIT**](#agrag-vectordb-milvus-MAX_RESPONSE_LIMIT) –

#### `agrag.vectordb.milvus.MAX_RESPONSE_LIMIT` \{#agrag-vectordb-milvus-MAX_RESPONSE_LIMIT}

```python
MAX_RESPONSE_LIMIT = 16384
```

#### `agrag.vectordb.milvus.MilvusVectorStore` \{#agrag-vectordb-milvus-MilvusVectorStore}

```python
MilvusVectorStore(*, settings:MilvusSettings | None = None, client:Any | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[VectorStore](#agrag-vectordb-base-VectorStore)</code>

A `VectorStore` backed by Milvus, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Milvus performs BM25 server-side, so hybrid
search needs no client-side sparse embedder; the sparse vector is computed
by a Milvus `Function` from the `text` field on write and at query time.

**Functions:**

- [**close**](#agrag-vectordb-milvus-MilvusVectorStore-close) – Release the backend connection.
- [**collection_exists**](#agrag-vectordb-milvus-MilvusVectorStore-collection_exists) – Report whether a collection exists.
- [**commit_pending**](#agrag-vectordb-milvus-MilvusVectorStore-commit_pending) – Promote one job's staged records to committed records.
- [**count**](#agrag-vectordb-milvus-MilvusVectorStore-count) – Count records in a collection.
- [**delete**](#agrag-vectordb-milvus-MilvusVectorStore-delete) – Delete records by id.
- [**delete_collection**](#agrag-vectordb-milvus-MilvusVectorStore-delete_collection) – Delete a collection and all its entities.
- [**delete_pending**](#agrag-vectordb-milvus-MilvusVectorStore-delete_pending) – Delete one job's staged records, leaving committed records alone.
- [**ensure_collection**](#agrag-vectordb-milvus-MilvusVectorStore-ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag-vectordb-milvus-MilvusVectorStore-hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag-vectordb-milvus-MilvusVectorStore-initialize) – Check connectivity and authentication.
- [**invalidate_collection**](#agrag-vectordb-milvus-MilvusVectorStore-invalidate_collection) – Drop cached distance-metric knowledge of a collection.
- [**retrieve**](#agrag-vectordb-milvus-MilvusVectorStore-retrieve) – Fetch records by id.
- [**scroll**](#agrag-vectordb-milvus-MilvusVectorStore-scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag-vectordb-milvus-MilvusVectorStore-search) – Search by dense vector only.
- [**upsert**](#agrag-vectordb-milvus-MilvusVectorStore-upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[MilvusSettings](#agrag-vectordb-settings-MilvusSettings) | None</code>) – Milvus connection settings. Defaults to
  `MilvusSettings()`.
- **client** (<code>Any | None</code>) – A pre-built `AsyncMilvusClient`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.
- **tracer** (<code>Tracer | None</code>) – Opens this store's spans.

##### `agrag.vectordb.milvus.MilvusVectorStore.close` \{#agrag-vectordb-milvus-MilvusVectorStore-close}

```python
close() -> None
```

Release the backend connection.

##### `agrag.vectordb.milvus.MilvusVectorStore.collection_exists` \{#agrag-vectordb-milvus-MilvusVectorStore-collection_exists}

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

**Returns:**

- <code>bool</code> – `True` if the collection exists.

##### `agrag.vectordb.milvus.MilvusVectorStore.commit_pending` \{#agrag-vectordb-milvus-MilvusVectorStore-commit_pending}

```python
commit_pending(collection:str, *, job_id:UUID) -> None
```

Promote one job's staged records to committed records.

Each staged record is written under its real id, which replaces any
committed record with that id, and the staged copy is deleted.
Re-running after a failure finishes the remaining records.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The committed job whose records become visible.

##### `agrag.vectordb.milvus.MilvusVectorStore.count` \{#agrag-vectordb-milvus-MilvusVectorStore-count}

```python
count(collection:str, *, filters:dict[str, Any] | None = None, pending_job_id:UUID | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>str</code>) – The collection to count.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on scalar fields.
- **pending_job_id** (<code>UUID | None</code>) – Count only this job's staged records.

**Returns:**

- <code>int</code> – The number of matching records.

##### `agrag.vectordb.milvus.MilvusVectorStore.delete` \{#agrag-vectordb-milvus-MilvusVectorStore-delete}

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to delete from.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to delete.

##### `agrag.vectordb.milvus.MilvusVectorStore.delete_collection` \{#agrag-vectordb-milvus-MilvusVectorStore-delete_collection}

```python
delete_collection(name:str) -> None
```

Delete a collection and all its entities.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

##### `agrag.vectordb.milvus.MilvusVectorStore.delete_pending` \{#agrag-vectordb-milvus-MilvusVectorStore-delete_pending}

```python
delete_pending(collection:str, *, job_id:UUID) -> None
```

Delete one job's staged records, leaving committed records alone.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The rolled-back job whose records are deleted.

##### `agrag.vectordb.milvus.MilvusVectorStore.ensure_collection` \{#agrag-vectordb-milvus-MilvusVectorStore-ensure_collection}

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

Milvus performs BM25 server-side, so the sparse field and its `Function`
are always provisioned; the `hybrid` flag is accepted for interface
parity but is a no-op here. An existing collection must already carry
this same fixed schema, since `upsert` and `hybrid_search` always
read and write every field regardless of `hybrid`.

**Parameters:**

- **name** (<code>str</code>) – The collection name.
- **dimensions** (<code>int</code>) – The embedding dimension.
- **distance** (<code>[Distance](common.md#agrag-common-data_models-vector_record-Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>bool</code>) – Accepted for interface parity; ignored by Milvus.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag-vectordb-errors-CollectionDimensionMismatchError)</code> – The collection exists with a
  different dimension than `dimensions`.
- <code>[VectorStoreError](#agrag-vectordb-errors-VectorStoreError)</code> – The collection exists but is missing a field or
  index this adapter requires.

##### `agrag.vectordb.milvus.MilvusVectorStore.hybrid_search` \{#agrag-vectordb-milvus-MilvusVectorStore-hybrid_search}

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

Fusion uses Milvus's native weighted reranker, which normalizes each
request's scores before applying `alpha`.

**Parameters:**

- **collection** (<code>str</code>) – The collection to search.
- **query_vector** (<code>Sequence\[float\]</code>) – The dense query embedding.
- **query_text** (<code>str</code>) – The query text, matched by BM25.
- **limit** (<code>int</code>) – The maximum number of hits to return.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on scalar fields.
- **alpha** (<code>float</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword.

**Returns:**

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – The fused hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`, or `alpha` is outside `[0.0, 1.0]`.

##### `agrag.vectordb.milvus.MilvusVectorStore.initialize` \{#agrag-vectordb-milvus-MilvusVectorStore-initialize}

```python
initialize() -> None
```

Check connectivity and authentication.

##### `agrag.vectordb.milvus.MilvusVectorStore.invalidate_collection` \{#agrag-vectordb-milvus-MilvusVectorStore-invalidate_collection}

```python
invalidate_collection(name:str) -> None
```

Drop cached distance-metric knowledge of a collection.

This store caches a collection's distance metric after the first
call that resolves it, on the assumption that it alone (via
`ensure_collection`/`delete_collection`) owns the collection's
lifecycle for as long as this instance is in use. If something
outside this instance deletes and recreates a collection under the
same name with a different metric, call this first so the next call
re-resolves that collection's metric from the backend instead of
trusting the stale cache.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

##### `agrag.vectordb.milvus.MilvusVectorStore.retrieve` \{#agrag-vectordb-milvus-MilvusVectorStore-retrieve}

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

Requests at most `MAX_RESPONSE_LIMIT` ids per call, so a large
`ids` list cannot exceed Milvus's response-size ceiling in one
request the way sending every id at once would.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to fetch.

**Returns:**

- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – ids.

##### `agrag.vectordb.milvus.MilvusVectorStore.scroll` \{#agrag-vectordb-milvus-MilvusVectorStore-scroll}

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False, pending_job_id:UUID | None = None) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

Milvus rejects a query whose `offset + limit` exceeds
`MAX_RESPONSE_LIMIT`, so a numeric offset cannot page past that
many total records. Pages instead cursor on the `id` primary key:
each page filters on `id > page_offset` and orders by `id`
ascending, which needs no offset at all and so never hits that
window regardless of collection size. The explicit order is load
bearing: without it, an unordered query result could omit rows at or
below the next cursor, permanently skipping them on the next page.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **limit** (<code>int</code>) – The maximum number of records per page.
- **page_offset** (<code>str | None</code>) – The id cursor from a previous `scroll` call.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on scalar fields.
- **with_vectors** (<code>bool</code>) – Whether to return each record's vector.
- **pending_job_id** (<code>UUID | None</code>) – Read only this job's staged records.

**Returns:**

- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – The page of records and the next page cursor, or `None` at the
- <code>str | None</code> – end.

##### `agrag.vectordb.milvus.MilvusVectorStore.search` \{#agrag-vectordb-milvus-MilvusVectorStore-search}

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>str</code>) – The collection to search.
- **query_vector** (<code>Sequence\[float\]</code>) – The dense query embedding.
- **limit** (<code>int</code>) – The maximum number of hits to return.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on scalar fields.

**Returns:**

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`.

##### `agrag.vectordb.milvus.MilvusVectorStore.upsert` \{#agrag-vectordb-milvus-MilvusVectorStore-upsert}

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None) -> None
```

Write or overwrite records in a collection.

**Parameters:**

- **collection** (<code>str</code>) – The collection to write to.
- **records** (<code>Sequence\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>int</code>) – The number of records per backend write call. Must be
  positive.
- **pending_job_id** (<code>UUID | None</code>) – The in-flight job staging these records.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.

### `agrag.vectordb.pending` \{#agrag-vectordb-pending}

Pending-record bookkeeping shared by the VectorStore adapters.

A record written for an in-flight Cutover Job lands under a staging id, so a
committed record with the real id stays searchable until the job commits and
survives the job's rollback.

**Functions:**

- [**promote_record**](#agrag-vectordb-pending-promote_record) – Return the committed record a staged record stands for.
- [**stage_records**](#agrag-vectordb-pending-stage_records) – Return records ready to write for one job, or unchanged outside a job.

**Attributes:**

- [**PENDING_FLAG**](#agrag-vectordb-pending-PENDING_FLAG) – Payload boolean that is true while a record belongs to an in-flight job.
- [**PENDING_JOB_KEY**](#agrag-vectordb-pending-PENDING_JOB_KEY) – Payload key holding the id of the job that wrote a staged record.
- [**TARGET_ID_KEY**](#agrag-vectordb-pending-TARGET_ID_KEY) – Payload key holding the real id a staged record is promoted to.

#### `agrag.vectordb.pending.PENDING_FLAG` \{#agrag-vectordb-pending-PENDING_FLAG}

```python
PENDING_FLAG = '_pending'
```

Payload boolean that is true while a record belongs to an in-flight job.

#### `agrag.vectordb.pending.PENDING_JOB_KEY` \{#agrag-vectordb-pending-PENDING_JOB_KEY}

```python
PENDING_JOB_KEY = PENDING_JOB_ID_PROPERTY
```

Payload key holding the id of the job that wrote a staged record.

#### `agrag.vectordb.pending.TARGET_ID_KEY` \{#agrag-vectordb-pending-TARGET_ID_KEY}

```python
TARGET_ID_KEY = '_target_id'
```

Payload key holding the real id a staged record is promoted to.

#### `agrag.vectordb.pending.promote_record` \{#agrag-vectordb-pending-promote_record}

```python
promote_record(record:VectorRecord) -> VectorRecord
```

Return the committed record a staged record stands for.

**Parameters:**

- **record** (<code>[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)</code>) – A record read back from the store with a staging id.

**Returns:**

- <code>[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)</code> – A record under the real id, without the pending keys.

**Raises:**

- <code>KeyError</code> – The record carries no real id, so it is not staged.

#### `agrag.vectordb.pending.stage_records` \{#agrag-vectordb-pending-stage_records}

```python
stage_records(records:Sequence[VectorRecord], pending_job_id:UUID | None) -> list[VectorRecord]
```

Return records ready to write for one job, or unchanged outside a job.

**Parameters:**

- **records** (<code>Sequence\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code>) – The records the caller wants to write.
- **pending_job_id** (<code>UUID | None</code>) – The in-flight job's id. None writes the records as
  committed.

**Returns:**

- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – With a job id, copies under staging ids that carry the pending flag,
- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – the job id and the real id. Without one, the records unchanged.

### `agrag.vectordb.qdrant` \{#agrag-vectordb-qdrant}

Qdrant vector-store backend.

**Classes:**

- [**QdrantVectorStore**](#agrag-vectordb-qdrant-QdrantVectorStore) – A `VectorStore` backed by Qdrant, including native hybrid search.

#### `agrag.vectordb.qdrant.QdrantVectorStore` \{#agrag-vectordb-qdrant-QdrantVectorStore}

```python
QdrantVectorStore(*, settings:QdrantSettings | None = None, sparse_embedder:SparseEmbedder | None = None, client:Any | None = None, models:Any | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[VectorStore](#agrag-vectordb-base-VectorStore)</code>

A `VectorStore` backed by Qdrant, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Hybrid search builds its sparse query with a
`SparseEmbedder` that defaults to FastEmbed BM25 and loads only when a
hybrid call first runs, not at construction.

**Functions:**

- [**close**](#agrag-vectordb-qdrant-QdrantVectorStore-close) – Release the backend connection.
- [**collection_exists**](#agrag-vectordb-qdrant-QdrantVectorStore-collection_exists) – Report whether a collection exists.
- [**commit_pending**](#agrag-vectordb-qdrant-QdrantVectorStore-commit_pending) – Promote one job's staged records to committed records.
- [**count**](#agrag-vectordb-qdrant-QdrantVectorStore-count) – Count records in a collection.
- [**delete**](#agrag-vectordb-qdrant-QdrantVectorStore-delete) – Delete records by id.
- [**delete_collection**](#agrag-vectordb-qdrant-QdrantVectorStore-delete_collection) – Delete a collection and all its points.
- [**delete_pending**](#agrag-vectordb-qdrant-QdrantVectorStore-delete_pending) – Delete one job's staged records, leaving committed records alone.
- [**ensure_collection**](#agrag-vectordb-qdrant-QdrantVectorStore-ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag-vectordb-qdrant-QdrantVectorStore-hybrid_search) – Search by dense vector and keyword text, fused by a weighted blend.
- [**initialize**](#agrag-vectordb-qdrant-QdrantVectorStore-initialize) – Check connectivity and authentication.
- [**invalidate_collection**](#agrag-vectordb-qdrant-QdrantVectorStore-invalidate_collection) – Drop cached hybrid-state and distance-metric knowledge of a collection.
- [**retrieve**](#agrag-vectordb-qdrant-QdrantVectorStore-retrieve) – Fetch records by id.
- [**scroll**](#agrag-vectordb-qdrant-QdrantVectorStore-scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag-vectordb-qdrant-QdrantVectorStore-search) – Search by dense vector only.
- [**upsert**](#agrag-vectordb-qdrant-QdrantVectorStore-upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[QdrantSettings](#agrag-vectordb-settings-QdrantSettings) | None</code>) – Qdrant connection settings. Defaults to
  `QdrantSettings()`.
- **sparse_embedder** (<code>[SparseEmbedder](embedding.md#agrag-embedding-sparse_base-SparseEmbedder) | None</code>) – The sparse embedder hybrid search uses. Defaults to
  a lazily-built `FastEmbedBM25Embedder`.
- **client** (<code>Any | None</code>) – A pre-built `AsyncQdrantClient`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.
- **models** (<code>Any | None</code>) – The `qdrant_client.models` module, for tests. Pair with
  `client` so filter/payload helpers work without needing the
  real `qdrant_client` package installed at all.
- **tracer** (<code>Tracer | None</code>) – Opens this store's spans.

##### `agrag.vectordb.qdrant.QdrantVectorStore.close` \{#agrag-vectordb-qdrant-QdrantVectorStore-close}

```python
close() -> None
```

Release the backend connection.

##### `agrag.vectordb.qdrant.QdrantVectorStore.collection_exists` \{#agrag-vectordb-qdrant-QdrantVectorStore-collection_exists}

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

**Returns:**

- <code>bool</code> – `True` if the collection exists.

##### `agrag.vectordb.qdrant.QdrantVectorStore.commit_pending` \{#agrag-vectordb-qdrant-QdrantVectorStore-commit_pending}

```python
commit_pending(collection:str, *, job_id:UUID) -> None
```

Promote one job's staged records to committed records.

Each staged record is written under its real id, which replaces any
committed record with that id, and the staged copy is deleted.
Re-running after a failure finishes the remaining records.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The committed job whose records become visible.

##### `agrag.vectordb.qdrant.QdrantVectorStore.count` \{#agrag-vectordb-qdrant-QdrantVectorStore-count}

```python
count(collection:str, *, filters:dict[str, Any] | None = None, pending_job_id:UUID | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>str</code>) – The collection to count.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on payload fields.
- **pending_job_id** (<code>UUID | None</code>) – Count only this job's staged records.

**Returns:**

- <code>int</code> – The number of matching records.

##### `agrag.vectordb.qdrant.QdrantVectorStore.delete` \{#agrag-vectordb-qdrant-QdrantVectorStore-delete}

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to delete from.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to delete.

##### `agrag.vectordb.qdrant.QdrantVectorStore.delete_collection` \{#agrag-vectordb-qdrant-QdrantVectorStore-delete_collection}

```python
delete_collection(name:str) -> None
```

Delete a collection and all its points.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

##### `agrag.vectordb.qdrant.QdrantVectorStore.delete_pending` \{#agrag-vectordb-qdrant-QdrantVectorStore-delete_pending}

```python
delete_pending(collection:str, *, job_id:UUID) -> None
```

Delete one job's staged records, leaving committed records alone.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The rolled-back job whose records are deleted.

##### `agrag.vectordb.qdrant.QdrantVectorStore.ensure_collection` \{#agrag-vectordb-qdrant-QdrantVectorStore-ensure_collection}

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>str</code>) – The collection name.
- **dimensions** (<code>int</code>) – The embedding dimension.
- **distance** (<code>[Distance](common.md#agrag-common-data_models-vector_record-Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>bool</code>) – Whether to provision the named sparse vector hybrid search
  needs.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag-vectordb-errors-CollectionDimensionMismatchError)</code> – The collection exists with a
  different dimension than `dimensions`.
- <code>[VectorStoreError](#agrag-vectordb-errors-VectorStoreError)</code> – The collection exists without hybrid search
  support and `hybrid=True` was requested.

##### `agrag.vectordb.qdrant.QdrantVectorStore.hybrid_search` \{#agrag-vectordb-qdrant-QdrantVectorStore-hybrid_search}

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

- **collection** (<code>str</code>) – The collection to search.
- **query_vector** (<code>Sequence\[float\]</code>) – The dense query embedding.
- **query_text** (<code>str</code>) – The query text, matched by BM25.
- **limit** (<code>int</code>) – The maximum number of hits to return.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on payload fields.
- **alpha** (<code>float</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword.

**Returns:**

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – The blended hits, highest combined score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`, or `alpha` is outside `[0.0, 1.0]`.

##### `agrag.vectordb.qdrant.QdrantVectorStore.initialize` \{#agrag-vectordb-qdrant-QdrantVectorStore-initialize}

```python
initialize() -> None
```

Check connectivity and authentication.

##### `agrag.vectordb.qdrant.QdrantVectorStore.invalidate_collection` \{#agrag-vectordb-qdrant-QdrantVectorStore-invalidate_collection}

```python
invalidate_collection(name:str) -> None
```

Drop cached hybrid-state and distance-metric knowledge of a collection.

This store caches a collection's hybrid support and distance metric
after the first call that resolves them, on the assumption that it
alone (via `ensure_collection`/`delete_collection`) owns the
collection's lifecycle for as long as this instance is in use. If
something outside this instance deletes and recreates a collection
under the same name with different config, call this first so the
next call re-resolves that collection's state from the backend
instead of trusting the stale cache.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

##### `agrag.vectordb.qdrant.QdrantVectorStore.retrieve` \{#agrag-vectordb-qdrant-QdrantVectorStore-retrieve}

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to fetch.

**Returns:**

- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – ids.

##### `agrag.vectordb.qdrant.QdrantVectorStore.scroll` \{#agrag-vectordb-qdrant-QdrantVectorStore-scroll}

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False, pending_job_id:UUID | None = None) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **limit** (<code>int</code>) – The maximum number of records per page.
- **page_offset** (<code>str | None</code>) – The offset from a previous `scroll` call.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on payload fields.
- **with_vectors** (<code>bool</code>) – Whether to return each record's vector.
- **pending_job_id** (<code>UUID | None</code>) – Read only this job's staged records.

**Returns:**

- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – The page of records and the next page offset, or `None` at the
- <code>str | None</code> – end.

##### `agrag.vectordb.qdrant.QdrantVectorStore.search` \{#agrag-vectordb-qdrant-QdrantVectorStore-search}

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>str</code>) – The collection to search.
- **query_vector** (<code>Sequence\[float\]</code>) – The dense query embedding.
- **limit** (<code>int</code>) – The maximum number of hits to return.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`.

##### `agrag.vectordb.qdrant.QdrantVectorStore.upsert` \{#agrag-vectordb-qdrant-QdrantVectorStore-upsert}

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None) -> None
```

Write or overwrite records in a collection.

With `pending_job_id` the records are staged for that job.

When `collection` has sparse-vector support (created or previously
seen with `ensure_collection(..., hybrid=True)`), each record's
`payload["text"]` is also sparse-embedded and stored under the named
sparse vector, so `hybrid_search`'s keyword arm has real vectors to
match. A record with no `text` payload key gets an empty sparse
vector and only ever surfaces through the dense side of a hybrid
search.

**Parameters:**

- **collection** (<code>str</code>) – The collection to write to.
- **records** (<code>Sequence\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>int</code>) – The number of records per backend write call. Must be
  positive.
- **pending_job_id** (<code>UUID | None</code>) – The in-flight job staging these records.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.

### `agrag.vectordb.settings` \{#agrag-vectordb-settings}

Settings for vector-store backends.

**Classes:**

- [**MilvusSettings**](#agrag-vectordb-settings-MilvusSettings) – Milvus connection configuration.
- [**QdrantSettings**](#agrag-vectordb-settings-QdrantSettings) – Qdrant connection configuration.
- [**WeaviateSettings**](#agrag-vectordb-settings-WeaviateSettings) – Weaviate connection configuration.

#### `agrag.vectordb.settings.MilvusSettings` \{#agrag-vectordb-settings-MilvusSettings}

Bases: <code>BaseSettings</code>

Milvus connection configuration.

**Attributes:**

- [**uri**](#agrag-vectordb-settings-MilvusSettings-uri) (<code>str</code>) – The Milvus endpoint URI. Env: `MILVUS_URI`.
- [**token**](#agrag-vectordb-settings-MilvusSettings-token) (<code>str</code>) – The Milvus auth token. Empty string for an unauthenticated
  instance. Env: `MILVUS_TOKEN`.
- [**require_tls**](#agrag-vectordb-settings-MilvusSettings-require_tls) (<code>bool</code>) – When `True`, reject a plaintext `uri` to a
  non-local host even with no `token` configured. Off by default
  since many deployments run an unauthenticated Milvus on a
  private network and rely on network segmentation rather than
  transport encryption. Env: `MILVUS_REQUIRE_TLS`.

**Raises:**

- <code>ValueError</code> – `uri` is plaintext (`http`), points at a non-local
  host, and either `token` is set or `require_tls` is
  `True`. Use `https` for a remote Milvus instance.

##### `agrag.vectordb.settings.MilvusSettings.model_config` \{#agrag-vectordb-settings-MilvusSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='MILVUS_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

##### `agrag.vectordb.settings.MilvusSettings.require_tls` \{#agrag-vectordb-settings-MilvusSettings-require_tls}

```python
require_tls: bool = False
```

##### `agrag.vectordb.settings.MilvusSettings.token` \{#agrag-vectordb-settings-MilvusSettings-token}

```python
token: str = ''
```

##### `agrag.vectordb.settings.MilvusSettings.uri` \{#agrag-vectordb-settings-MilvusSettings-uri}

```python
uri: str = 'http://localhost:19530'
```

#### `agrag.vectordb.settings.QdrantSettings` \{#agrag-vectordb-settings-QdrantSettings}

Bases: <code>BaseSettings</code>

Qdrant connection configuration.

**Attributes:**

- [**url**](#agrag-vectordb-settings-QdrantSettings-url) (<code>str</code>) – The Qdrant endpoint URL. Env: `QDRANT_URL`.
- [**api_key**](#agrag-vectordb-settings-QdrantSettings-api_key) (<code>str</code>) – The Qdrant API key. Env: `QDRANT_API_KEY`.
- [**require_tls**](#agrag-vectordb-settings-QdrantSettings-require_tls) (<code>bool</code>) – When `True`, reject a plaintext `url` to a non-local
  host even with no `api_key` configured. Off by default since
  many deployments run an unauthenticated Qdrant on a private
  network and rely on network segmentation rather than transport
  encryption. Env: `QDRANT_REQUIRE_TLS`.

**Raises:**

- <code>ValueError</code> – `url` is plaintext (`http`), points at a non-local
  host, and either `api_key` is set or `require_tls` is
  `True`. Use `https` for a remote Qdrant instance.

##### `agrag.vectordb.settings.QdrantSettings.api_key` \{#agrag-vectordb-settings-QdrantSettings-api_key}

```python
api_key: str = ''
```

##### `agrag.vectordb.settings.QdrantSettings.model_config` \{#agrag-vectordb-settings-QdrantSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='QDRANT_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

##### `agrag.vectordb.settings.QdrantSettings.require_tls` \{#agrag-vectordb-settings-QdrantSettings-require_tls}

```python
require_tls: bool = False
```

##### `agrag.vectordb.settings.QdrantSettings.url` \{#agrag-vectordb-settings-QdrantSettings-url}

```python
url: str = 'http://localhost:6333'
```

#### `agrag.vectordb.settings.WeaviateSettings` \{#agrag-vectordb-settings-WeaviateSettings}

Bases: <code>BaseSettings</code>

Weaviate connection configuration.

**Attributes:**

- [**mode**](#agrag-vectordb-settings-WeaviateSettings-mode) (<code>Literal['cloud', 'custom']</code>) – `"cloud"` connects to Weaviate Cloud. `"custom"` connects to
  a self-hosted instance (used by integration tests against the local
  Docker Compose instance) — an explicit field, not inferred from the
  URL, since inference caused real connection bugs in surveyed
  reference implementations. Env: `WEAVIATE_MODE`.
- [**url**](#agrag-vectordb-settings-WeaviateSettings-url) (<code>str</code>) – The Weaviate endpoint URL. For `"cloud"`, the cluster URL. For
  `"custom"`, the full host URL. Env: `WEAVIATE_URL`.
- [**api_key**](#agrag-vectordb-settings-WeaviateSettings-api_key) (<code>str</code>) – The Weaviate API key. Env: `WEAVIATE_API_KEY`.
- [**grpc_port**](#agrag-vectordb-settings-WeaviateSettings-grpc_port) (<code>int</code>) – The gRPC port, used by `"custom"` mode only (`"cloud"`
  mode infers it). Env: `WEAVIATE_GRPC_PORT`.
- [**require_tls**](#agrag-vectordb-settings-WeaviateSettings-require_tls) (<code>bool</code>) – When `True`, reject a plaintext `url` to a non-local
  host even with no `api_key` configured. Off by default since
  many deployments run an unauthenticated Weaviate on a private
  network and rely on network segmentation rather than transport
  encryption. Env: `WEAVIATE_REQUIRE_TLS`.

**Raises:**

- <code>ValueError</code> – `url` is plaintext (`http`), points at a non-local
  host, and either `api_key` is set or `require_tls` is
  `True`. Use `https` for a remote Weaviate instance.

##### `agrag.vectordb.settings.WeaviateSettings.api_key` \{#agrag-vectordb-settings-WeaviateSettings-api_key}

```python
api_key: str = ''
```

##### `agrag.vectordb.settings.WeaviateSettings.grpc_port` \{#agrag-vectordb-settings-WeaviateSettings-grpc_port}

```python
grpc_port: int = 50051
```

##### `agrag.vectordb.settings.WeaviateSettings.mode` \{#agrag-vectordb-settings-WeaviateSettings-mode}

```python
mode: Literal['cloud', 'custom'] = 'custom'
```

##### `agrag.vectordb.settings.WeaviateSettings.model_config` \{#agrag-vectordb-settings-WeaviateSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='WEAVIATE_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

##### `agrag.vectordb.settings.WeaviateSettings.require_tls` \{#agrag-vectordb-settings-WeaviateSettings-require_tls}

```python
require_tls: bool = False
```

##### `agrag.vectordb.settings.WeaviateSettings.url` \{#agrag-vectordb-settings-WeaviateSettings-url}

```python
url: str = 'http://localhost:8080'
```

### `agrag.vectordb.weaviate` \{#agrag-vectordb-weaviate}

Weaviate vector-store backend.

**Classes:**

- [**WeaviateVectorStore**](#agrag-vectordb-weaviate-WeaviateVectorStore) – A `VectorStore` backed by Weaviate, including native hybrid search.

#### `agrag.vectordb.weaviate.WeaviateVectorStore` \{#agrag-vectordb-weaviate-WeaviateVectorStore}

```python
WeaviateVectorStore(*, settings:WeaviateSettings | None = None, client:Any | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[VectorStore](#agrag-vectordb-base-VectorStore)</code>

A `VectorStore` backed by Weaviate, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Weaviate does its own server-side BM25, so
hybrid search needs no client-side sparse embedder.

**Functions:**

- [**close**](#agrag-vectordb-weaviate-WeaviateVectorStore-close) – Release the backend connection.
- [**collection_exists**](#agrag-vectordb-weaviate-WeaviateVectorStore-collection_exists) – Report whether a collection exists.
- [**commit_pending**](#agrag-vectordb-weaviate-WeaviateVectorStore-commit_pending) – Promote one job's staged records to committed records.
- [**count**](#agrag-vectordb-weaviate-WeaviateVectorStore-count) – Count records in a collection.
- [**delete**](#agrag-vectordb-weaviate-WeaviateVectorStore-delete) – Delete records by id.
- [**delete_collection**](#agrag-vectordb-weaviate-WeaviateVectorStore-delete_collection) – Delete a collection and all its objects.
- [**delete_pending**](#agrag-vectordb-weaviate-WeaviateVectorStore-delete_pending) – Delete one job's staged records, leaving committed records alone.
- [**ensure_collection**](#agrag-vectordb-weaviate-WeaviateVectorStore-ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag-vectordb-weaviate-WeaviateVectorStore-hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag-vectordb-weaviate-WeaviateVectorStore-initialize) – Open the connection and check authentication.
- [**retrieve**](#agrag-vectordb-weaviate-WeaviateVectorStore-retrieve) – Fetch records by id.
- [**scroll**](#agrag-vectordb-weaviate-WeaviateVectorStore-scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag-vectordb-weaviate-WeaviateVectorStore-search) – Search by dense vector only.
- [**upsert**](#agrag-vectordb-weaviate-WeaviateVectorStore-upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[WeaviateSettings](#agrag-vectordb-settings-WeaviateSettings) | None</code>) – Weaviate connection settings. Defaults to
  `WeaviateSettings()`.
- **client** (<code>Any | None</code>) – A pre-built Weaviate async client, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.
- **tracer** (<code>Tracer | None</code>) – Opens this store's spans.

##### `agrag.vectordb.weaviate.WeaviateVectorStore.close` \{#agrag-vectordb-weaviate-WeaviateVectorStore-close}

```python
close() -> None
```

Release the backend connection.

##### `agrag.vectordb.weaviate.WeaviateVectorStore.collection_exists` \{#agrag-vectordb-weaviate-WeaviateVectorStore-collection_exists}

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

**Returns:**

- <code>bool</code> – `True` if the collection exists.

##### `agrag.vectordb.weaviate.WeaviateVectorStore.commit_pending` \{#agrag-vectordb-weaviate-WeaviateVectorStore-commit_pending}

```python
commit_pending(collection:str, *, job_id:UUID) -> None
```

Promote one job's staged records to committed records.

Each staged record is written under its real id, which replaces any
committed record with that id, and the staged copy is deleted.
Re-running after a failure finishes the remaining records.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The committed job whose records become visible.

##### `agrag.vectordb.weaviate.WeaviateVectorStore.count` \{#agrag-vectordb-weaviate-WeaviateVectorStore-count}

```python
count(collection:str, *, filters:dict[str, Any] | None = None, pending_job_id:UUID | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>str</code>) – The collection to count.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on payload fields.
- **pending_job_id** (<code>UUID | None</code>) – Count only this job's staged records.

**Returns:**

- <code>int</code> – The number of matching records.

##### `agrag.vectordb.weaviate.WeaviateVectorStore.delete` \{#agrag-vectordb-weaviate-WeaviateVectorStore-delete}

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to delete from.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to delete.

##### `agrag.vectordb.weaviate.WeaviateVectorStore.delete_collection` \{#agrag-vectordb-weaviate-WeaviateVectorStore-delete_collection}

```python
delete_collection(name:str) -> None
```

Delete a collection and all its objects.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

##### `agrag.vectordb.weaviate.WeaviateVectorStore.delete_pending` \{#agrag-vectordb-weaviate-WeaviateVectorStore-delete_pending}

```python
delete_pending(collection:str, *, job_id:UUID) -> None
```

Delete one job's staged records, leaving committed records alone.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The rolled-back job whose records are deleted.

##### `agrag.vectordb.weaviate.WeaviateVectorStore.ensure_collection` \{#agrag-vectordb-weaviate-WeaviateVectorStore-ensure_collection}

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>str</code>) – The collection name.
- **dimensions** (<code>int</code>) – The embedding dimension.
- **distance** (<code>[Distance](common.md#agrag-common-data_models-vector_record-Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>bool</code>) – No-op for Weaviate, which needs no sparse provisioning.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag-vectordb-errors-CollectionDimensionMismatchError)</code> – An existing object in the
  collection carries a vector of a different dimension. Weaviate
  keeps no schema-level dimension for self-provided vectors, so
  an existing collection with no vector-bearing object cannot be
  checked this way.

##### `agrag.vectordb.weaviate.WeaviateVectorStore.hybrid_search` \{#agrag-vectordb-weaviate-WeaviateVectorStore-hybrid_search}

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

**Parameters:**

- **collection** (<code>str</code>) – The collection to search.
- **query_vector** (<code>Sequence\[float\]</code>) – The dense query embedding.
- **query_text** (<code>str</code>) – The query text, matched by keyword/BM25.
- **limit** (<code>int</code>) – The maximum number of hits to return.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on payload fields.
- **alpha** (<code>float</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword.

**Returns:**

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – The fused hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`, or `alpha` is outside `[0.0, 1.0]`.

##### `agrag.vectordb.weaviate.WeaviateVectorStore.initialize` \{#agrag-vectordb-weaviate-WeaviateVectorStore-initialize}

```python
initialize() -> None
```

Open the connection and check authentication.

##### `agrag.vectordb.weaviate.WeaviateVectorStore.retrieve` \{#agrag-vectordb-weaviate-WeaviateVectorStore-retrieve}

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to fetch.

**Returns:**

- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – ids.

##### `agrag.vectordb.weaviate.WeaviateVectorStore.scroll` \{#agrag-vectordb-weaviate-WeaviateVectorStore-scroll}

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False, pending_job_id:UUID | None = None) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

Weaviate rejects a cursor (`after`) combined with a filter, and
every read here carries the pending filter, so pages use a numeric
offset. Weaviate caps `offset + limit` at its
`QUERY_MAXIMUM_RESULTS` setting, 10000 by default.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **limit** (<code>int</code>) – The maximum number of records per page.
- **page_offset** (<code>str | None</code>) – The offset from a previous `scroll` call.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on payload fields.
- **with_vectors** (<code>bool</code>) – Whether to return each record's vector.
- **pending_job_id** (<code>UUID | None</code>) – Read only this job's staged records.

**Returns:**

- <code>list\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code> – The page of records and the next page offset, or `None` at the
- <code>str | None</code> – end.

##### `agrag.vectordb.weaviate.WeaviateVectorStore.search` \{#agrag-vectordb-weaviate-WeaviateVectorStore-search}

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>str</code>) – The collection to search.
- **query_vector** (<code>Sequence\[float\]</code>) – The dense query embedding.
- **limit** (<code>int</code>) – The maximum number of hits to return.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>list\[[VectorHit](common.md#agrag-common-data_models-vector_record-VectorHit)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`.

##### `agrag.vectordb.weaviate.WeaviateVectorStore.upsert` \{#agrag-vectordb-weaviate-WeaviateVectorStore-upsert}

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None) -> None
```

Write or overwrite records in a collection.

Uses Weaviate's batch import, which replaces an existing object
sharing a written id instead of rejecting it, giving real
insert-or-replace semantics and per-call batching in one request.

**Parameters:**

- **collection** (<code>str</code>) – The collection to write to.
- **records** (<code>Sequence\[[VectorRecord](common.md#agrag-common-data_models-vector_record-VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>int</code>) – The number of records per backend write call. Must be
  positive.
- **pending_job_id** (<code>UUID | None</code>) – The in-flight job staging these records.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.
- <code>[VectorStoreError](#agrag-vectordb-errors-VectorStoreError)</code> – At least one record in a batch failed to write.
