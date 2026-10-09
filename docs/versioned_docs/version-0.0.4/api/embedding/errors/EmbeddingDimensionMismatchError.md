---
title: agrag.embedding.errors.EmbeddingDimensionMismatchError
sidebar_label: EmbeddingDimensionMismatchError
---

# `agrag.embedding.errors.EmbeddingDimensionMismatchError` \{#agrag-embedding-errors-EmbeddingDimensionMismatchError}

```python
EmbeddingDimensionMismatchError(*, expected:int, actual:int) -> None
```

Bases: <code>[EmbeddingError](EmbeddingError.md)</code>

A stored collection or index expects a different embedding dimension.

**Attributes:**

- [**expected**](#agrag-embedding-errors-EmbeddingDimensionMismatchError-expected) – The dimension the collection or index was created with.
- [**actual**](#agrag-embedding-errors-EmbeddingDimensionMismatchError-actual) – The dimension the embedder actually produces.

## `actual` \{#agrag-embedding-errors-EmbeddingDimensionMismatchError-actual}

```python
actual = actual
```

## `expected` \{#agrag-embedding-errors-EmbeddingDimensionMismatchError-expected}

```python
expected = expected
```
