---
title: agrag.vectordb.milvus.MilvusVectorStore
sidebar_label: MilvusVectorStore
---

# `agrag.vectordb.milvus.MilvusVectorStore` \{#agrag-vectordb-milvus-MilvusVectorStore}

```python
MilvusVectorStore(*, settings:MilvusSettings | None = None, client:Any | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[VectorStore](../base/VectorStore.md)</code>

A `VectorStore` backed by Milvus, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Milvus performs BM25 server-side, so hybrid
search needs no client-side sparse embedder; the sparse vector is computed
by a Milvus `Function` from the `text` field on write and at query time.

**Functions:**

- [**close**](#agrag-vectordb-milvus-MilvusVectorStore-close) – Release the backend connection.
- [**collection_exists**](#agrag-vectordb-milvus-MilvusVectorStore-collection_exists) – Report whether a collection exists.
- [**count**](#agrag-vectordb-milvus-MilvusVectorStore-count) – Count records in a collection.
- [**delete**](#agrag-vectordb-milvus-MilvusVectorStore-delete) – Delete records by id.
- [**delete_collection**](#agrag-vectordb-milvus-MilvusVectorStore-delete_collection) – Delete a collection and all its entities.
- [**ensure_collection**](#agrag-vectordb-milvus-MilvusVectorStore-ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag-vectordb-milvus-MilvusVectorStore-hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag-vectordb-milvus-MilvusVectorStore-initialize) – Check connectivity and authentication.
- [**invalidate_collection**](#agrag-vectordb-milvus-MilvusVectorStore-invalidate_collection) – Drop cached distance-metric knowledge of a collection.
- [**retrieve**](#agrag-vectordb-milvus-MilvusVectorStore-retrieve) – Fetch records by id.
- [**scroll**](#agrag-vectordb-milvus-MilvusVectorStore-scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag-vectordb-milvus-MilvusVectorStore-search) – Search by dense vector only.
- [**upsert**](#agrag-vectordb-milvus-MilvusVectorStore-upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[MilvusSettings](../settings/MilvusSettings.md) | None</code>) – Milvus connection settings. Defaults to
  `MilvusSettings()`.
- **client** (<code>Any | None</code>) – A pre-built `AsyncMilvusClient`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.
- **tracer** (<code>Tracer | None</code>) – Opens this store's spans.

## `close` \{#agrag-vectordb-milvus-MilvusVectorStore-close}

```python
close() -> None
```

Release the backend connection.

## `collection_exists` \{#agrag-vectordb-milvus-MilvusVectorStore-collection_exists}

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

**Returns:**

- <code>bool</code> – `True` if the collection exists.

## `count` \{#agrag-vectordb-milvus-MilvusVectorStore-count}

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>str</code>) – The collection to count.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on scalar fields.

**Returns:**

- <code>int</code> – The number of matching records.

## `delete` \{#agrag-vectordb-milvus-MilvusVectorStore-delete}

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to delete from.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to delete.

## `delete_collection` \{#agrag-vectordb-milvus-MilvusVectorStore-delete_collection}

```python
delete_collection(name:str) -> None
```

Delete a collection and all its entities.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

## `ensure_collection` \{#agrag-vectordb-milvus-MilvusVectorStore-ensure_collection}

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
- **distance** (<code>[Distance](../../common/data_models/vector_record/Distance.md)</code>) – The distance metric new collections use.
- **hybrid** (<code>bool</code>) – Accepted for interface parity; ignored by Milvus.

**Raises:**

- <code>[CollectionDimensionMismatchError](../errors/CollectionDimensionMismatchError.md)</code> – The collection exists with a
  different dimension than `dimensions`.
- <code>[VectorStoreError](../errors/VectorStoreError.md)</code> – The collection exists but is missing a field or
  index this adapter requires.

## `hybrid_search` \{#agrag-vectordb-milvus-MilvusVectorStore-hybrid_search}

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

- <code>list\[[VectorHit](../../common/data_models/vector_record/VectorHit.md)\]</code> – The fused hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`, or `alpha` is outside `[0.0, 1.0]`.

## `initialize` \{#agrag-vectordb-milvus-MilvusVectorStore-initialize}

```python
initialize() -> None
```

Check connectivity and authentication.

## `invalidate_collection` \{#agrag-vectordb-milvus-MilvusVectorStore-invalidate_collection}

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

## `retrieve` \{#agrag-vectordb-milvus-MilvusVectorStore-retrieve}

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

- <code>list\[[VectorRecord](../../common/data_models/vector_record/VectorRecord.md)\]</code> – The records that exist, in the requested order, omitting missing
- <code>list\[[VectorRecord](../../common/data_models/vector_record/VectorRecord.md)\]</code> – ids.

## `scroll` \{#agrag-vectordb-milvus-MilvusVectorStore-scroll}

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
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

**Returns:**

- <code>list\[[VectorRecord](../../common/data_models/vector_record/VectorRecord.md)\]</code> – The page of records and the next page cursor, or `None` at the
- <code>str | None</code> – end.

## `search` \{#agrag-vectordb-milvus-MilvusVectorStore-search}

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

- <code>list\[[VectorHit](../../common/data_models/vector_record/VectorHit.md)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`.

## `upsert` \{#agrag-vectordb-milvus-MilvusVectorStore-upsert}

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Write or overwrite records in a collection.

**Parameters:**

- **collection** (<code>str</code>) – The collection to write to.
- **records** (<code>Sequence\[[VectorRecord](../../common/data_models/vector_record/VectorRecord.md)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>int</code>) – The number of records per backend write call. Must be
  positive.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.
