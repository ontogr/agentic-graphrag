---
title: agrag.vectordb.base.VectorStore
sidebar_label: VectorStore
---

# `agrag.vectordb.base.VectorStore` \{#agrag-vectordb-base-VectorStore}

Bases: <code>ABC</code>

A vector database backend: collection lifecycle, writes, and search.

**Functions:**

- [**close**](#agrag-vectordb-base-VectorStore-close) – Release the backend connection.
- [**collection_exists**](#agrag-vectordb-base-VectorStore-collection_exists) – Report whether a collection exists.
- [**count**](#agrag-vectordb-base-VectorStore-count) – Count records in a collection.
- [**delete**](#agrag-vectordb-base-VectorStore-delete) – Delete records by id.
- [**delete_collection**](#agrag-vectordb-base-VectorStore-delete_collection) – Delete a collection and all its points.
- [**ensure_collection**](#agrag-vectordb-base-VectorStore-ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag-vectordb-base-VectorStore-hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag-vectordb-base-VectorStore-initialize) – Check connectivity and authentication.
- [**retrieve**](#agrag-vectordb-base-VectorStore-retrieve) – Fetch records by id.
- [**scroll**](#agrag-vectordb-base-VectorStore-scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag-vectordb-base-VectorStore-search) – Search by dense vector only.
- [**upsert**](#agrag-vectordb-base-VectorStore-upsert) – Write or overwrite records in a collection.

## `close` \{#agrag-vectordb-base-VectorStore-close}

```python
close() -> None
```

Release the backend connection.

## `collection_exists` \{#agrag-vectordb-base-VectorStore-collection_exists}

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

**Returns:**

- <code>bool</code> – `True` if the collection exists.

## `count` \{#agrag-vectordb-base-VectorStore-count}

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

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

**Returns:**

- <code>int</code> – The number of matching records.

## `delete` \{#agrag-vectordb-base-VectorStore-delete}

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>str</code>) – The collection to delete from.
- **ids** (<code>Sequence\[UUID\]</code>) – The ids to delete.

## `delete_collection` \{#agrag-vectordb-base-VectorStore-delete_collection}

```python
delete_collection(name:str) -> None
```

Delete a collection and all its points.

**Parameters:**

- **name** (<code>str</code>) – The collection name.

## `ensure_collection` \{#agrag-vectordb-base-VectorStore-ensure_collection}

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>str</code>) – The collection name.
- **dimensions** (<code>int</code>) – The embedding dimension. If the collection already
  exists with a different dimension, this raises.
- **distance** (<code>[Distance](../../common/data_models/vector_record/Distance.md)</code>) – The distance metric new collections use.
- **hybrid** (<code>bool</code>) – Whether to additionally provision the sparse-vector
  configuration hybrid search needs. Ignored by backends that
  need no such provisioning.

**Raises:**

- <code>[CollectionDimensionMismatchError](../errors/CollectionDimensionMismatchError.md)</code> – The collection exists with a
  different dimension than `dimensions`.

## `hybrid_search` \{#agrag-vectordb-base-VectorStore-hybrid_search}

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

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

- <code>list\[[VectorHit](../../common/data_models/vector_record/VectorHit.md)\]</code> – The fused hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `agrag.common.validation.MAX_SEARCH_LIMIT`, or `alpha` is
  outside `[0.0, 1.0]`. Enforced uniformly across backends
  since they otherwise fail differently outside that range.

## `initialize` \{#agrag-vectordb-base-VectorStore-initialize}

```python
initialize() -> None
```

Check connectivity and authentication.

**Raises:**

- <code>[VectorStoreError](../errors/VectorStoreError.md)</code> – The backend is unreachable, or the credentials
  are rejected.

## `retrieve` \{#agrag-vectordb-base-VectorStore-retrieve}

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

## `scroll` \{#agrag-vectordb-base-VectorStore-scroll}

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

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

**Returns:**

- <code>list\[[VectorRecord](../../common/data_models/vector_record/VectorRecord.md)\]</code> – The page of records and the next page offset, or `None` at the
- <code>str | None</code> – end.

## `search` \{#agrag-vectordb-base-VectorStore-search}

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

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

- <code>list\[[VectorHit](../../common/data_models/vector_record/VectorHit.md)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>ValueError</code> – `limit` is not positive, or exceeds
  `agrag.common.validation.MAX_SEARCH_LIMIT`. Enforced
  uniformly across backends since they otherwise fail
  differently outside that range.

## `upsert` \{#agrag-vectordb-base-VectorStore-upsert}

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
