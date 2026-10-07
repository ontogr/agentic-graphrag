---
title: agrag.vectordb.CollectionDimensionMismatchError
sidebar_label: CollectionDimensionMismatchError
---

# `agrag.vectordb.CollectionDimensionMismatchError` \{#agrag-vectordb-CollectionDimensionMismatchError}

```python
CollectionDimensionMismatchError(*, expected:int, actual:int) -> None
```

Bases: <code>[VectorStoreError](errors/VectorStoreError.md)</code>

A collection already exists with a different embedding dimension.

**Attributes:**

- [**expected**](#agrag-vectordb-CollectionDimensionMismatchError-expected) – The dimension the collection was created with.
- [**actual**](#agrag-vectordb-CollectionDimensionMismatchError-actual) – The dimension the caller requested.

## `actual` \{#agrag-vectordb-CollectionDimensionMismatchError-actual}

```python
actual = actual
```

## `expected` \{#agrag-vectordb-CollectionDimensionMismatchError-expected}

```python
expected = expected
```
