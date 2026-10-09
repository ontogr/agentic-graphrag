---
title: agrag.vectordb.errors.CollectionDimensionMismatchError
sidebar_label: CollectionDimensionMismatchError
---

# `agrag.vectordb.errors.CollectionDimensionMismatchError` \{#agrag-vectordb-errors-CollectionDimensionMismatchError}

```python
CollectionDimensionMismatchError(*, expected:int, actual:int) -> None
```

Bases: <code>[VectorStoreError](VectorStoreError.md)</code>

A collection already exists with a different embedding dimension.

**Attributes:**

- [**expected**](#agrag-vectordb-errors-CollectionDimensionMismatchError-expected) – The dimension the collection was created with.
- [**actual**](#agrag-vectordb-errors-CollectionDimensionMismatchError-actual) – The dimension the caller requested.

## `actual` \{#agrag-vectordb-errors-CollectionDimensionMismatchError-actual}

```python
actual = actual
```

## `expected` \{#agrag-vectordb-errors-CollectionDimensionMismatchError-expected}

```python
expected = expected
```
