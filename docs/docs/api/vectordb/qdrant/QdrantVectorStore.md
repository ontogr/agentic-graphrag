---
title: agrag.vectordb.qdrant.QdrantVectorStore
sidebar_label: QdrantVectorStore
---

# `agrag.vectordb.qdrant.QdrantVectorStore` \{#agrag-vectordb-qdrant-QdrantVectorStore}

```python
QdrantVectorStore(*, settings:QdrantSettings | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[VectorStore](../base/VectorStore.md)</code>

An exclusive vector index on Qdrant 1.17 or newer.

BM25 inference runs locally through FastEmbed, not Qdrant Cloud. Hybrid
queries use weighted reciprocal rank fusion. Dense scores have graph-native
scale; hybrid scores are ranks only. Searches accept at most 16384 results.

**Parameters:**

- **settings** (<code>[QdrantSettings](QdrantSettings.md) | None</code>) – Connection settings and the required per-graph prefix.
- **tracer** (<code>Tracer | None</code>) – Opens spans without recording credentials or embedded text.

**Functions:**

- [**close**](#agrag-vectordb-qdrant-QdrantVectorStore-close) – Release connections; a later initialize can reconnect.
- [**collection_info**](#agrag-vectordb-qdrant-QdrantVectorStore-collection_info) – Return exact count and dense configuration, or None when absent.
- [**collection_name**](#agrag-vectordb-qdrant-QdrantVectorStore-collection_name) – Return the prefixed collection name for a kind.
- [**delete**](#agrag-vectordb-qdrant-QdrantVectorStore-delete) – Delete in batches of 256 and wait for the changes to become visible.
- [**delete_collection**](#agrag-vectordb-qdrant-QdrantVectorStore-delete_collection) – Remove a collection; an absent collection is already deleted.
- [**ensure_collection**](#agrag-vectordb-qdrant-QdrantVectorStore-ensure_collection) – Create both vector indexes or reject a mismatched existing index.
- [**hybrid_search**](#agrag-vectordb-qdrant-QdrantVectorStore-hybrid_search) – Fuse dense and BM25 ranks; alpha endpoints select one leg exactly.
- [**initialize**](#agrag-vectordb-qdrant-QdrantVectorStore-initialize) – Connect once, authenticate and check that the server is reachable.
- [**list_ids**](#agrag-vectordb-qdrant-QdrantVectorStore-list_ids) – Page ascending UUIDs, excluding the cursor even if it still exists.
- [**search**](#agrag-vectordb-qdrant-QdrantVectorStore-search) – Return dense hits on the graph-native score scale.
- [**upsert**](#agrag-vectordb-qdrant-QdrantVectorStore-upsert) – Overwrite records, waiting for each dense and BM25 batch to be applied.

**Attributes:**

- [**collection_prefix**](#agrag-vectordb-qdrant-QdrantVectorStore-collection_prefix) –
- [**max_results**](#agrag-vectordb-qdrant-QdrantVectorStore-max_results) –
- [**name**](#agrag-vectordb-qdrant-QdrantVectorStore-name) (<code>str</code>) –

## `close` \{#agrag-vectordb-qdrant-QdrantVectorStore-close}

```python
close() -> None
```

Release connections; a later initialize can reconnect.

## `collection_info` \{#agrag-vectordb-qdrant-QdrantVectorStore-collection_info}

```python
collection_info(kind:VectorKind) -> CollectionInfo | None
```

Return exact count and dense configuration, or None when absent.

## `collection_name` \{#agrag-vectordb-qdrant-QdrantVectorStore-collection_name}

```python
collection_name(kind:VectorKind) -> str
```

Return the prefixed collection name for a kind.

## `collection_prefix` \{#agrag-vectordb-qdrant-QdrantVectorStore-collection_prefix}

```python
collection_prefix = self._settings.collection_prefix
```

## `delete` \{#agrag-vectordb-qdrant-QdrantVectorStore-delete}

```python
delete(kind:VectorKind, ids:Sequence[UUID]) -> None
```

Delete in batches of 256 and wait for the changes to become visible.

## `delete_collection` \{#agrag-vectordb-qdrant-QdrantVectorStore-delete_collection}

```python
delete_collection(kind:VectorKind) -> None
```

Remove a collection; an absent collection is already deleted.

## `ensure_collection` \{#agrag-vectordb-qdrant-QdrantVectorStore-ensure_collection}

```python
ensure_collection(kind:VectorKind, *, dimensions:int, distance:Distance) -> None
```

Create both vector indexes or reject a mismatched existing index.

## `hybrid_search` \{#agrag-vectordb-qdrant-QdrantVectorStore-hybrid_search}

```python
hybrid_search(kind:VectorKind, vector:Sequence[float], text:str, *, limit:int, alpha:float, labels:Sequence[str] | None = None) -> list[VectorHit]
```

Fuse dense and BM25 ranks; alpha endpoints select one leg exactly.

## `initialize` \{#agrag-vectordb-qdrant-QdrantVectorStore-initialize}

```python
initialize() -> None
```

Connect once, authenticate and check that the server is reachable.

## `list_ids` \{#agrag-vectordb-qdrant-QdrantVectorStore-list_ids}

```python
list_ids(kind:VectorKind, *, after:UUID | None = None, limit:int = 1000) -> list[UUID]
```

Page ascending UUIDs, excluding the cursor even if it still exists.

## `max_results` \{#agrag-vectordb-qdrant-QdrantVectorStore-max_results}

```python
max_results = MAX_SEARCH_LIMIT
```

## `name` \{#agrag-vectordb-qdrant-QdrantVectorStore-name}

```python
name: str = 'qdrant'
```

## `search` \{#agrag-vectordb-qdrant-QdrantVectorStore-search}

```python
search(kind:VectorKind, vector:Sequence[float], *, limit:int, labels:Sequence[str] | None = None) -> list[VectorHit]
```

Return dense hits on the graph-native score scale.

## `upsert` \{#agrag-vectordb-qdrant-QdrantVectorStore-upsert}

```python
upsert(kind:VectorKind, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Overwrite records, waiting for each dense and BM25 batch to be applied.
