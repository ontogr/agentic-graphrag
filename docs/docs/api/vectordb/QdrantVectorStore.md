---
title: agrag.vectordb.QdrantVectorStore
sidebar_label: QdrantVectorStore
---

# `agrag.vectordb.QdrantVectorStore` \{#agrag-vectordb-QdrantVectorStore}

```python
QdrantVectorStore(*, settings:QdrantSettings | None = None, sparse_embedder:SparseEmbedder | None = None, client:Any | None = None, models:Any | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[VectorStore](base/VectorStore.md)</code>

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

- **settings** (<code>[QdrantSettings](settings/QdrantSettings.md) | None</code>) – Qdrant connection settings. Defaults to
  `QdrantSettings()`.
- **sparse_embedder** (<code>[SparseEmbedder](../embedding/sparse_base/SparseEmbedder.md) | None</code>) – The sparse embedder hybrid search uses. Defaults to
  a lazily-built `FastEmbedBM25Embedder`.
- **client** (<code>Any | None</code>) – A pre-built `AsyncQdrantClient`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.
- **models** (<code>Any | None</code>) – The `qdrant_client.models` module, for tests. Pair with
  `client` so filter/payload helpers work without needing the
  real `qdrant_client` package installed at all.
- **tracer** (<code>Tracer | None</code>) – Opens this store's spans.

## `close` \{#agrag-vectordb-QdrantVectorStore-close}

```python
close() -> None
```

Release the backend connection.

## `collection_exists` \{#agrag-vectordb-QdrantVectorStore-collection_exists}

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

**Returns:**

- <code>bool</code> – `True` if the collection exists.

## `commit_pending` \{#agrag-vectordb-QdrantVectorStore-commit_pending}

```python
commit_pending(collection:str, *, job_id:UUID) -> None
```

Promote one job's staged records to committed records.

Each staged record is written under its real id, which replaces any
committed record with that id, and the staged copy is deleted. The
method reads the first page of staged records again after each
delete, so it needs no offset. Re-running after a failure finishes
the remaining records.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The committed job whose records become visible.

**Raises:**

- <code>RuntimeError</code> – A delete left the same staged records in place.

## `count` \{#agrag-vectordb-QdrantVectorStore-count}

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

## `delete` \{#agrag-vectordb-QdrantVectorStore-delete}

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to delete from.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to delete.

## `delete_collection` \{#agrag-vectordb-QdrantVectorStore-delete_collection}

```python
delete_collection(name:str) -> None
```

Delete a collection and all its points.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

## `delete_pending` \{#agrag-vectordb-QdrantVectorStore-delete_pending}

```python
delete_pending(collection:str, *, job_id:UUID) -> None
```

Delete one job's staged records, leaving committed records alone.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The rolled-back job whose records are deleted.

**Raises:**

- <code>RuntimeError</code> – A delete left the same staged records in place.

## `ensure_collection` \{#agrag-vectordb-QdrantVectorStore-ensure_collection}

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>str</code>) – The collection name.
- **dimensions** (<code>int</code>) – The embedding dimension.
- **distance** (<code>[Distance](../common/data_models/vector_record/Distance.md)</code>) – The distance metric new collections use.
- **hybrid** (<code>bool</code>) – Whether to provision the named sparse vector hybrid search
  needs.

**Raises:**

- <code>[CollectionDimensionMismatchError](errors/CollectionDimensionMismatchError.md)</code> – The collection exists with a
  different dimension than `dimensions`.
- <code>[VectorStoreError](errors/VectorStoreError.md)</code> – The collection exists without hybrid search
  support and `hybrid=True` was requested.

## `hybrid_search` \{#agrag-vectordb-QdrantVectorStore-hybrid_search}

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

- <code>list\[[VectorHit](../common/data_models/vector_record/VectorHit.md)\]</code> – The blended hits, highest combined score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`, or `alpha` is outside `[0.0, 1.0]`.

## `initialize` \{#agrag-vectordb-QdrantVectorStore-initialize}

```python
initialize() -> None
```

Check connectivity and authentication.

## `invalidate_collection` \{#agrag-vectordb-QdrantVectorStore-invalidate_collection}

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

## `retrieve` \{#agrag-vectordb-QdrantVectorStore-retrieve}

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to fetch.

**Returns:**

- <code>list\[[VectorRecord](../common/data_models/vector_record/VectorRecord.md)\]</code> – The records that exist, in the requested order, omitting missing
- <code>list\[[VectorRecord](../common/data_models/vector_record/VectorRecord.md)\]</code> – ids.

## `scroll` \{#agrag-vectordb-QdrantVectorStore-scroll}

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

- <code>list\[[VectorRecord](../common/data_models/vector_record/VectorRecord.md)\]</code> – The page of records and the next page offset, or `None` at the
- <code>str | None</code> – end.

## `search` \{#agrag-vectordb-QdrantVectorStore-search}

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

- <code>list\[[VectorHit](../common/data_models/vector_record/VectorHit.md)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`.

## `upsert` \{#agrag-vectordb-QdrantVectorStore-upsert}

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
- **records** (<code>Sequence\[[VectorRecord](../common/data_models/vector_record/VectorRecord.md)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>int</code>) – The number of records per backend write call. Must be
  positive.
- **pending_job_id** (<code>UUID | None</code>) – The in-flight job staging these records.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive, or a payload uses a
  key the store reserves for pending records (`_pending`,
  `_pending_job_id`, `_target_id`).
