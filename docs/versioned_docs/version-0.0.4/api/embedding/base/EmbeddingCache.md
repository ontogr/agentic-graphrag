---
title: agrag.embedding.base.EmbeddingCache
sidebar_label: EmbeddingCache
---

# `agrag.embedding.base.EmbeddingCache` \{#agrag-embedding-base-EmbeddingCache}

Bases: <code>ABC</code>

A content-addressed cache for embedding vectors.

`normalize` is part of the cache key alongside `text` and `model`
because it changes the vector an embedder produces for the same text and
model: without it, embedders sharing one cache but configured with
opposite `EmbeddingSettings.normalize` values would read back the wrong
output mode. Any future embedder setting that changes output values must
join this key the same way.

**Functions:**

- [**get**](#agrag-embedding-base-EmbeddingCache-get) – Return the cached vector for `(text, model, normalize)`.
- [**set**](#agrag-embedding-base-EmbeddingCache-set) – Store `vector` under `(text, model, normalize)`.

## `get` \{#agrag-embedding-base-EmbeddingCache-get}

```python
get(*, text:str, model:str, normalize:bool) -> list[float] | None
```

Return the cached vector for `(text, model, normalize)`.

**Returns:**

- <code>list\[float\] | None</code> – The cached vector, or `None` on a miss.

## `set` \{#agrag-embedding-base-EmbeddingCache-set}

```python
set(*, text:str, model:str, normalize:bool, vector:list[float]) -> None
```

Store `vector` under `(text, model, normalize)`.
