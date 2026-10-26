---
title: agrag.vectordb.weaviate.WeaviateVectorStore
sidebar_label: WeaviateVectorStore
---

# `agrag.vectordb.weaviate.WeaviateVectorStore` \{#agrag-vectordb-weaviate-WeaviateVectorStore}

```python
WeaviateVectorStore(*, settings:WeaviateSettings | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[VectorStore](../base/VectorStore.md)</code>

An exclusive external index backed by Weaviate.

Collections persist dimensions in their description, including when empty.
Changing that description outside this adapter invalidates the collection.
Dense scores use the graph-native scale. Hybrid scores are rank-only.
Server-side asynchronous indexing must be disabled for read-after-write
consistency. Each collection belongs to exactly one graph.

**Functions:**

- [**close**](#agrag-vectordb-weaviate-WeaviateVectorStore-close) – Close connections after all requests have finished.
- [**collection_info**](#agrag-vectordb-weaviate-WeaviateVectorStore-collection_info) – Return persisted dimensions, actual metric and count, or None if absent.
- [**collection_name**](#agrag-vectordb-weaviate-WeaviateVectorStore-collection_name) – Capitalize only the first letter of the prefixed collection name.
- [**delete**](#agrag-vectordb-weaviate-WeaviateVectorStore-delete) – Delete in batches of at most 500 IDs, ignoring missing records.
- [**delete_collection**](#agrag-vectordb-weaviate-WeaviateVectorStore-delete_collection) – Delete a collection, ignoring one that does not exist.
- [**ensure_collection**](#agrag-vectordb-weaviate-WeaviateVectorStore-ensure_collection) – Create a collection or reject incompatible dimensions and metric.
- [**hybrid_search**](#agrag-vectordb-weaviate-WeaviateVectorStore-hybrid_search) – Fuse dense and BM25 ranks, with exact dense and lexical endpoints.
- [**initialize**](#agrag-vectordb-weaviate-WeaviateVectorStore-initialize) – Connect and verify readiness, raising VectorStoreError on failure.
- [**list_ids**](#agrag-vectordb-weaviate-WeaviateVectorStore-list_ids) – Return ascending IDs strictly after the cursor, independent of scan order.
- [**search**](#agrag-vectordb-weaviate-WeaviateVectorStore-search) – Return dense matches on the graph-native score scale, best first.
- [**upsert**](#agrag-vectordb-weaviate-WeaviateVectorStore-upsert) – Insert or replace UUIDs in batches, checking every batch response.

**Attributes:**

- [**collection_prefix**](#agrag-vectordb-weaviate-WeaviateVectorStore-collection_prefix) –
- [**max_results**](#agrag-vectordb-weaviate-WeaviateVectorStore-max_results) (<code>int</code>) –
- [**name**](#agrag-vectordb-weaviate-WeaviateVectorStore-name) (<code>str</code>) –

**Parameters:**

- **settings** (<code>[WeaviateSettings](WeaviateSettings.md) | None</code>) – Connection settings and the graph's collection prefix.
- **tracer** (<code>Tracer | None</code>) – Emits database client spans when supplied. None disables
  tracing even when a global provider is configured.

## `close` \{#agrag-vectordb-weaviate-WeaviateVectorStore-close}

```python
close() -> None
```

Close connections after all requests have finished.

The caller owns request lifetimes and must await active operations
before closing the store. Repeated calls are harmless.

## `collection_info` \{#agrag-vectordb-weaviate-WeaviateVectorStore-collection_info}

```python
collection_info(kind:VectorKind, *, exact_count:bool = True) -> CollectionInfo | None
```

Return persisted dimensions, actual metric and count, or None if absent.

**Parameters:**

- **kind** (<code>[VectorKind](../../common/data_models/vector_record/VectorKind.md)</code>) – The collection to describe.
- **exact_count** (<code>bool</code>) – Also fetch a sample vector to verify its dimensions. When
  false, only schema metadata and the object count are read.

## `collection_name` \{#agrag-vectordb-weaviate-WeaviateVectorStore-collection_name}

```python
collection_name(kind:VectorKind) -> str
```

Capitalize only the first letter of the prefixed collection name.

## `collection_prefix` \{#agrag-vectordb-weaviate-WeaviateVectorStore-collection_prefix}

```python
collection_prefix = self._settings.collection_prefix
```

## `delete` \{#agrag-vectordb-weaviate-WeaviateVectorStore-delete}

```python
delete(kind:VectorKind, ids:Sequence[UUID]) -> None
```

Delete in batches of at most 500 IDs, ignoring missing records.

## `delete_collection` \{#agrag-vectordb-weaviate-WeaviateVectorStore-delete_collection}

```python
delete_collection(kind:VectorKind) -> None
```

Delete a collection, ignoring one that does not exist.

## `ensure_collection` \{#agrag-vectordb-weaviate-WeaviateVectorStore-ensure_collection}

```python
ensure_collection(kind:VectorKind, *, dimensions:int, distance:Distance) -> None
```

Create a collection or reject incompatible dimensions and metric.

An existing collection without adapter-owned dimension metadata is
rejected rather than silently adopted. DOT raises ValueError.

## `hybrid_search` \{#agrag-vectordb-weaviate-WeaviateVectorStore-hybrid_search}

```python
hybrid_search(kind:VectorKind, vector:Sequence[float], text:str, *, limit:int, alpha:float, labels:Sequence[str] | None = None) -> list[VectorHit]
```

Fuse dense and BM25 ranks, with exact dense and lexical endpoints.

## `initialize` \{#agrag-vectordb-weaviate-WeaviateVectorStore-initialize}

```python
initialize() -> None
```

Connect and verify readiness, raising VectorStoreError on failure.

## `list_ids` \{#agrag-vectordb-weaviate-WeaviateVectorStore-list_ids}

```python
list_ids(kind:VectorKind, *, after:UUID | None = None, limit:int = 1000) -> list[UUID]
```

Return ascending IDs strictly after the cursor, independent of scan order.

Scans all UUIDs with the server cursor and retains only the smallest
requested page. Memory is bounded by the page size for all collections.

## `max_results` \{#agrag-vectordb-weaviate-WeaviateVectorStore-max_results}

```python
max_results: int = 10000
```

## `name` \{#agrag-vectordb-weaviate-WeaviateVectorStore-name}

```python
name: str = 'weaviate'
```

## `search` \{#agrag-vectordb-weaviate-WeaviateVectorStore-search}

```python
search(kind:VectorKind, vector:Sequence[float], *, limit:int, labels:Sequence[str] | None = None) -> list[VectorHit]
```

Return dense matches on the graph-native score scale, best first.

## `upsert` \{#agrag-vectordb-weaviate-WeaviateVectorStore-upsert}

```python
upsert(kind:VectorKind, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Insert or replace UUIDs in batches, checking every batch response.

Missing collections and wrong vector dimensions raise VectorStoreError.
Batch import replaces an object with an existing UUID in Weaviate.
