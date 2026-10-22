---
title: agrag.vectordb.milvus.MilvusVectorStore
sidebar_label: MilvusVectorStore
---

# `agrag.vectordb.milvus.MilvusVectorStore` \{#agrag-vectordb-milvus-MilvusVectorStore}

```python
MilvusVectorStore(settings:MilvusSettings | None = None, *, tracer:Tracer | None = None) -> None
```

Bases: <code>[VectorStore](../base/VectorStore.md)</code>

Store UUID-keyed vectors with server-generated BM25 sparse vectors.

Dense scores match graph-native cosine and Euclidean scores. Hybrid scores
use Milvus's normalized weighted ranking; alpha endpoints use a single search
path so a zero-weight path cannot add hits. All reads use Strong consistency.

**Functions:**

- [**close**](#agrag-vectordb-milvus-MilvusVectorStore-close) – Release the connection; a later initialize reconnects.
- [**collection_info**](#agrag-vectordb-milvus-MilvusVectorStore-collection_info) – Return schema metadata and a Strong count, including unflushed writes.
- [**collection_name**](#agrag-vectordb-milvus-MilvusVectorStore-collection_name) – Return the prefixed collection name for a kind.
- [**delete**](#agrag-vectordb-milvus-MilvusVectorStore-delete) – Delete in batches, ignoring absent IDs and collections.
- [**delete_collection**](#agrag-vectordb-milvus-MilvusVectorStore-delete_collection) – Drop a collection if it exists.
- [**ensure_collection**](#agrag-vectordb-milvus-MilvusVectorStore-ensure_collection) – Create and load a collection, or reject dimension and metric mismatches.
- [**hybrid_search**](#agrag-vectordb-milvus-MilvusVectorStore-hybrid_search) – Fuse normalized dense and BM25 scores; endpoints select one path only.
- [**initialize**](#agrag-vectordb-milvus-MilvusVectorStore-initialize) – Connect and authenticate, reporting failures without credential values.
- [**list_ids**](#agrag-vectordb-milvus-MilvusVectorStore-list_ids) – Page UUIDs in ascending order with an exclusive keyset cursor.
- [**search**](#agrag-vectordb-milvus-MilvusVectorStore-search) – Return dense hits with graph-native scores, best first.
- [**upsert**](#agrag-vectordb-milvus-MilvusVectorStore-upsert) – Overwrite records by UUID, truncating only stored BM25 text to 65535 bytes.

**Attributes:**

- [**collection_prefix**](#agrag-vectordb-milvus-MilvusVectorStore-collection_prefix) –
- [**max_results**](#agrag-vectordb-milvus-MilvusVectorStore-max_results) (<code>int</code>) –
- [**name**](#agrag-vectordb-milvus-MilvusVectorStore-name) (<code>str</code>) –
- [**settings**](#agrag-vectordb-milvus-MilvusVectorStore-settings) –

## `close` \{#agrag-vectordb-milvus-MilvusVectorStore-close}

```python
close() -> None
```

Release the connection; a later initialize reconnects.

## `collection_info` \{#agrag-vectordb-milvus-MilvusVectorStore-collection_info}

```python
collection_info(kind:VectorKind) -> CollectionInfo | None
```

Return schema metadata and a Strong count, including unflushed writes.

## `collection_name` \{#agrag-vectordb-milvus-MilvusVectorStore-collection_name}

```python
collection_name(kind:VectorKind) -> str
```

Return the prefixed collection name for a kind.

## `collection_prefix` \{#agrag-vectordb-milvus-MilvusVectorStore-collection_prefix}

```python
collection_prefix = self.settings.collection_prefix
```

## `delete` \{#agrag-vectordb-milvus-MilvusVectorStore-delete}

```python
delete(kind:VectorKind, ids:Sequence[UUID]) -> None
```

Delete in batches, ignoring absent IDs and collections.

A server failure can leave earlier batches applied. Retry the same IDs
to finish an interrupted deletion; deleting an absent ID is harmless.

## `delete_collection` \{#agrag-vectordb-milvus-MilvusVectorStore-delete_collection}

```python
delete_collection(kind:VectorKind) -> None
```

Drop a collection if it exists.

## `ensure_collection` \{#agrag-vectordb-milvus-MilvusVectorStore-ensure_collection}

```python
ensure_collection(kind:VectorKind, *, dimensions:int, distance:Distance) -> None
```

Create and load a collection, or reject dimension and metric mismatches.

## `hybrid_search` \{#agrag-vectordb-milvus-MilvusVectorStore-hybrid_search}

```python
hybrid_search(kind:VectorKind, vector:Sequence[float], text:str, *, limit:int, alpha:float, labels:Sequence[str] | None = None) -> list[VectorHit]
```

Fuse normalized dense and BM25 scores; endpoints select one path only.

## `initialize` \{#agrag-vectordb-milvus-MilvusVectorStore-initialize}

```python
initialize() -> None
```

Connect and authenticate, reporting failures without credential values.

## `list_ids` \{#agrag-vectordb-milvus-MilvusVectorStore-list_ids}

```python
list_ids(kind:VectorKind, *, after:UUID | None = None, limit:int = 1000) -> list[UUID]
```

Page UUIDs in ascending order with an exclusive keyset cursor.

Milvus 3.0 sorting orders the canonical VARCHAR UUIDs lexicographically,
which is also UUID numeric order. Pages do not form a concurrent snapshot.

## `max_results` \{#agrag-vectordb-milvus-MilvusVectorStore-max_results}

```python
max_results: int = 16384
```

## `name` \{#agrag-vectordb-milvus-MilvusVectorStore-name}

```python
name: str = 'milvus'
```

## `search` \{#agrag-vectordb-milvus-MilvusVectorStore-search}

```python
search(kind:VectorKind, vector:Sequence[float], *, limit:int, labels:Sequence[str] | None = None) -> list[VectorHit]
```

Return dense hits with graph-native scores, best first.

## `settings` \{#agrag-vectordb-milvus-MilvusVectorStore-settings}

```python
settings = settings if settings is not None else MilvusSettings()
```

## `upsert` \{#agrag-vectordb-milvus-MilvusVectorStore-upsert}

```python
upsert(kind:VectorKind, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Overwrite records by UUID, truncating only stored BM25 text to 65535 bytes.

UTF-8 truncation preserves whole characters. The input records and dense
vectors remain unchanged. A warning is emitted once per truncated call.
Labels allow at most 4096 values, each at most 256 UTF-8 bytes. Invalid
labels raise ValueError before any batch is written. A server failure can
leave earlier batches applied; retrying the same records is idempotent.
