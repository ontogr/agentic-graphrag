---
title: agrag.vectordb.base.VectorStore
sidebar_label: VectorStore
---

# `agrag.vectordb.base.VectorStore` \{#agrag-vectordb-base-VectorStore}

Bases: <code>ABC</code>

An external index whose hits must be joined to visible graph nodes.

Writes are idempotent and immediately visible on the same client. Reads and
deletes of missing collections return empty results. Dense scores use
`(1 + cosine) / 2` or `1 / (1 + squared_distance)`. Hybrid scores are
rank-only, with alpha one selecting dense order and zero lexical order.
Lexical-only search omits records that do not match the query text.
Labels filter by any overlap. Search limits above max_results are rejected.

**Functions:**

- [**close**](#agrag-vectordb-base-VectorStore-close) – Release the client's connections.
- [**collection_info**](#agrag-vectordb-base-VectorStore-collection_info) – Return collection metadata, or None if it does not exist.
- [**collection_name**](#agrag-vectordb-base-VectorStore-collection_name) – Return the prefixed collection name for a kind.
- [**delete**](#agrag-vectordb-base-VectorStore-delete) – Delete ids, ignoring ids and collections that do not exist.
- [**delete_collection**](#agrag-vectordb-base-VectorStore-delete_collection) – Delete the collection, doing nothing when it does not exist.
- [**ensure_collection**](#agrag-vectordb-base-VectorStore-ensure_collection) – Create a collection or reject dimension or distance mismatches.
- [**hybrid_search**](#agrag-vectordb-base-VectorStore-hybrid_search) – Return dense and lexical hits fused by alpha, in descending rank.
- [**initialize**](#agrag-vectordb-base-VectorStore-initialize) – Connect and authenticate, raising VectorStoreError on failure.
- [**list_ids**](#agrag-vectordb-base-VectorStore-list_ids) – Return ids in ascending order, strictly after the exclusive cursor.
- [**search**](#agrag-vectordb-base-VectorStore-search) – Return at most limit dense hits, best first, with graph-native scores.
- [**upsert**](#agrag-vectordb-base-VectorStore-upsert) – Overwrite records by id; raise VectorStoreError if collection is absent.

**Attributes:**

- [**collection_prefix**](#agrag-vectordb-base-VectorStore-collection_prefix) (<code>str</code>) –
- [**max_results**](#agrag-vectordb-base-VectorStore-max_results) (<code>int</code>) –
- [**name**](#agrag-vectordb-base-VectorStore-name) (<code>str</code>) –

## `close` \{#agrag-vectordb-base-VectorStore-close}

```python
close() -> None
```

Release the client's connections.

## `collection_info` \{#agrag-vectordb-base-VectorStore-collection_info}

```python
collection_info(kind:VectorKind) -> CollectionInfo | None
```

Return collection metadata, or None if it does not exist.

## `collection_name` \{#agrag-vectordb-base-VectorStore-collection_name}

```python
collection_name(kind:VectorKind) -> str
```

Return the prefixed collection name for a kind.

## `collection_prefix` \{#agrag-vectordb-base-VectorStore-collection_prefix}

```python
collection_prefix: str
```

## `delete` \{#agrag-vectordb-base-VectorStore-delete}

```python
delete(kind:VectorKind, ids:Sequence[UUID]) -> None
```

Delete ids, ignoring ids and collections that do not exist.

## `delete_collection` \{#agrag-vectordb-base-VectorStore-delete_collection}

```python
delete_collection(kind:VectorKind) -> None
```

Delete the collection, doing nothing when it does not exist.

## `ensure_collection` \{#agrag-vectordb-base-VectorStore-ensure_collection}

```python
ensure_collection(kind:VectorKind, *, dimensions:int, distance:Distance) -> None
```

Create a collection or reject dimension or distance mismatches.

DOT distance is unsupported and raises ValueError.

## `hybrid_search` \{#agrag-vectordb-base-VectorStore-hybrid_search}

```python
hybrid_search(kind:VectorKind, vector:Sequence[float], text:str, *, limit:int, alpha:float, labels:Sequence[str] | None = None) -> list[VectorHit]
```

Return dense and lexical hits fused by alpha, in descending rank.

## `initialize` \{#agrag-vectordb-base-VectorStore-initialize}

```python
initialize() -> None
```

Connect and authenticate, raising VectorStoreError on failure.

## `list_ids` \{#agrag-vectordb-base-VectorStore-list_ids}

```python
list_ids(kind:VectorKind, *, after:UUID | None = None, limit:int = 1000) -> list[UUID]
```

Return ids in ascending order, strictly after the exclusive cursor.

## `max_results` \{#agrag-vectordb-base-VectorStore-max_results}

```python
max_results: int
```

## `name` \{#agrag-vectordb-base-VectorStore-name}

```python
name: str
```

## `search` \{#agrag-vectordb-base-VectorStore-search}

```python
search(kind:VectorKind, vector:Sequence[float], *, limit:int, labels:Sequence[str] | None = None) -> list[VectorHit]
```

Return at most limit dense hits, best first, with graph-native scores.

## `upsert` \{#agrag-vectordb-base-VectorStore-upsert}

```python
upsert(kind:VectorKind, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Overwrite records by id; raise VectorStoreError if collection is absent.
