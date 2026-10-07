---
title: agrag.vectordb.WeaviateVectorStore
sidebar_label: WeaviateVectorStore
---

# `agrag.vectordb.WeaviateVectorStore` \{#agrag-vectordb-WeaviateVectorStore}

```python
WeaviateVectorStore(*, settings:WeaviateSettings | None = None, client:Any | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[VectorStore](base/VectorStore.md)</code>

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

- **settings** (<code>[WeaviateSettings](settings/WeaviateSettings.md) | None</code>) – Weaviate connection settings. Defaults to
  `WeaviateSettings()`.
- **client** (<code>Any | None</code>) – A pre-built Weaviate async client, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.
- **tracer** (<code>Tracer | None</code>) – Opens this store's spans.

## `close` \{#agrag-vectordb-WeaviateVectorStore-close}

```python
close() -> None
```

Release the backend connection.

## `collection_exists` \{#agrag-vectordb-WeaviateVectorStore-collection_exists}

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

**Returns:**

- <code>bool</code> – `True` if the collection exists.

## `commit_pending` \{#agrag-vectordb-WeaviateVectorStore-commit_pending}

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

## `count` \{#agrag-vectordb-WeaviateVectorStore-count}

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

## `delete` \{#agrag-vectordb-WeaviateVectorStore-delete}

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to delete from.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to delete.

## `delete_collection` \{#agrag-vectordb-WeaviateVectorStore-delete_collection}

```python
delete_collection(name:str) -> None
```

Delete a collection and all its objects.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

## `delete_pending` \{#agrag-vectordb-WeaviateVectorStore-delete_pending}

```python
delete_pending(collection:str, *, job_id:UUID) -> None
```

Delete one job's staged records, leaving committed records alone.

**Parameters:**

- **collection** (<code>str</code>) – The collection the job wrote to.
- **job_id** (<code>UUID</code>) – The rolled-back job whose records are deleted.

**Raises:**

- <code>RuntimeError</code> – A delete left the same staged records in place.

## `ensure_collection` \{#agrag-vectordb-WeaviateVectorStore-ensure_collection}

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>str</code>) – The collection name.
- **dimensions** (<code>int</code>) – The embedding dimension.
- **distance** (<code>[Distance](../common/data_models/vector_record/Distance.md)</code>) – The distance metric new collections use.
- **hybrid** (<code>bool</code>) – No-op for Weaviate, which needs no sparse provisioning.

**Raises:**

- <code>[CollectionDimensionMismatchError](errors/CollectionDimensionMismatchError.md)</code> – An existing object in the
  collection carries a vector of a different dimension. Weaviate
  keeps no schema-level dimension for self-provided vectors, so
  an existing collection with no vector-bearing object cannot be
  checked this way.

## `hybrid_search` \{#agrag-vectordb-WeaviateVectorStore-hybrid_search}

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

- <code>list\[[VectorHit](../common/data_models/vector_record/VectorHit.md)\]</code> – The fused hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`, or `alpha` is outside `[0.0, 1.0]`.

## `initialize` \{#agrag-vectordb-WeaviateVectorStore-initialize}

```python
initialize() -> None
```

Open the connection and check authentication.

## `retrieve` \{#agrag-vectordb-WeaviateVectorStore-retrieve}

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

## `scroll` \{#agrag-vectordb-WeaviateVectorStore-scroll}

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

- <code>list\[[VectorRecord](../common/data_models/vector_record/VectorRecord.md)\]</code> – The page of records and the next page offset, or `None` at the
- <code>str | None</code> – end.

## `search` \{#agrag-vectordb-WeaviateVectorStore-search}

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

## `upsert` \{#agrag-vectordb-WeaviateVectorStore-upsert}

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256, pending_job_id:UUID | None = None) -> None
```

Write or overwrite records in a collection.

Uses Weaviate's batch import, which replaces an existing object
sharing a written id instead of rejecting it, giving real
insert-or-replace semantics and per-call batching in one request.

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
- <code>[VectorStoreError](errors/VectorStoreError.md)</code> – At least one record in a batch failed to write.
