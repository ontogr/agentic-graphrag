---
title: agrag.vectordb.weaviate.WeaviateVectorStore
sidebar_label: WeaviateVectorStore
---

# `agrag.vectordb.weaviate.WeaviateVectorStore` \{#agrag-vectordb-weaviate-WeaviateVectorStore}

```python
WeaviateVectorStore(*, settings:WeaviateSettings | None = None, client:Any | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[VectorStore](../base/VectorStore.md)</code>

A `VectorStore` backed by Weaviate, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Weaviate does its own server-side BM25, so
hybrid search needs no client-side sparse embedder.

**Functions:**

- [**close**](#agrag-vectordb-weaviate-WeaviateVectorStore-close) – Release the backend connection.
- [**collection_exists**](#agrag-vectordb-weaviate-WeaviateVectorStore-collection_exists) – Report whether a collection exists.
- [**count**](#agrag-vectordb-weaviate-WeaviateVectorStore-count) – Count records in a collection.
- [**delete**](#agrag-vectordb-weaviate-WeaviateVectorStore-delete) – Delete records by id.
- [**delete_collection**](#agrag-vectordb-weaviate-WeaviateVectorStore-delete_collection) – Delete a collection and all its objects.
- [**ensure_collection**](#agrag-vectordb-weaviate-WeaviateVectorStore-ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag-vectordb-weaviate-WeaviateVectorStore-hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag-vectordb-weaviate-WeaviateVectorStore-initialize) – Open the connection and check authentication.
- [**retrieve**](#agrag-vectordb-weaviate-WeaviateVectorStore-retrieve) – Fetch records by id.
- [**scroll**](#agrag-vectordb-weaviate-WeaviateVectorStore-scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag-vectordb-weaviate-WeaviateVectorStore-search) – Search by dense vector only.
- [**upsert**](#agrag-vectordb-weaviate-WeaviateVectorStore-upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[WeaviateSettings](../settings/WeaviateSettings.md) | None</code>) – Weaviate connection settings. Defaults to
  `WeaviateSettings()`.
- **client** (<code>Any | None</code>) – A pre-built Weaviate async client, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.
- **tracer** (<code>Tracer | None</code>) – Opens this store's spans.

## `close` \{#agrag-vectordb-weaviate-WeaviateVectorStore-close}

```python
close() -> None
```

Release the backend connection.

## `collection_exists` \{#agrag-vectordb-weaviate-WeaviateVectorStore-collection_exists}

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

**Returns:**

- <code>bool</code> – `True` if the collection exists.

## `count` \{#agrag-vectordb-weaviate-WeaviateVectorStore-count}

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>str</code>) – The collection to count.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>int</code> – The number of matching records.

## `delete` \{#agrag-vectordb-weaviate-WeaviateVectorStore-delete}

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to delete from.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to delete.

## `delete_collection` \{#agrag-vectordb-weaviate-WeaviateVectorStore-delete_collection}

```python
delete_collection(name:str) -> None
```

Delete a collection and all its objects.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

## `ensure_collection` \{#agrag-vectordb-weaviate-WeaviateVectorStore-ensure_collection}

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>str</code>) – The collection name.
- **dimensions** (<code>int</code>) – The embedding dimension.
- **distance** (<code>[Distance](../../common/data_models/vector_record/Distance.md)</code>) – The distance metric new collections use.
- **hybrid** (<code>bool</code>) – No-op for Weaviate, which needs no sparse provisioning.

**Raises:**

- <code>[CollectionDimensionMismatchError](../errors/CollectionDimensionMismatchError.md)</code> – An existing object in the
  collection carries a vector of a different dimension. Weaviate
  keeps no schema-level dimension for self-provided vectors, so
  an existing collection with no vector-bearing object cannot be
  checked this way.

## `hybrid_search` \{#agrag-vectordb-weaviate-WeaviateVectorStore-hybrid_search}

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

- <code>list\[[VectorHit](../../common/data_models/vector_record/VectorHit.md)\]</code> – The fused hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`, or `alpha` is outside `[0.0, 1.0]`.

## `initialize` \{#agrag-vectordb-weaviate-WeaviateVectorStore-initialize}

```python
initialize() -> None
```

Open the connection and check authentication.

## `retrieve` \{#agrag-vectordb-weaviate-WeaviateVectorStore-retrieve}

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to fetch.

**Returns:**

- <code>list\[[VectorRecord](../../common/data_models/vector_record/VectorRecord.md)\]</code> – The records that exist, in the requested order, omitting missing
- <code>list\[[VectorRecord](../../common/data_models/vector_record/VectorRecord.md)\]</code> – ids.

## `scroll` \{#agrag-vectordb-weaviate-WeaviateVectorStore-scroll}

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

**Parameters:**

- **collection** (<code>str</code>) – The collection to read.
- **limit** (<code>int</code>) – The maximum number of records per page.
- **page_offset** (<code>str | None</code>) – The cursor id from a previous `scroll` call.
- **filters** (<code>dict\[str, Any\] | None</code>) – A flat-dict filter on payload fields.
- **with_vectors** (<code>bool</code>) – Whether to return each record's vector.

**Returns:**

- <code>list\[[VectorRecord](../../common/data_models/vector_record/VectorRecord.md)\]</code> – The page of records and the next page cursor, or `None` at the
- <code>str | None</code> – end.

## `search` \{#agrag-vectordb-weaviate-WeaviateVectorStore-search}

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

- <code>list\[[VectorHit](../../common/data_models/vector_record/VectorHit.md)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`.

## `upsert` \{#agrag-vectordb-weaviate-WeaviateVectorStore-upsert}

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Write or overwrite records in a collection.

Uses Weaviate's batch import, which replaces an existing object
sharing a written id instead of rejecting it, giving real
insert-or-replace semantics and per-call batching in one request.

**Parameters:**

- **collection** (<code>str</code>) – The collection to write to.
- **records** (<code>Sequence\[[VectorRecord](../../common/data_models/vector_record/VectorRecord.md)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>int</code>) – The number of records per backend write call. Must be
  positive.

**Raises:**

- <code>ValueError</code> – `batch_size` is not positive.
- <code>[VectorStoreError](../errors/VectorStoreError.md)</code> – At least one record in a batch failed to write.
