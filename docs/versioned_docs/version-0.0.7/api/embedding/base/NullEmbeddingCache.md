---
title: agrag.embedding.base.NullEmbeddingCache
sidebar_label: NullEmbeddingCache
---

# `agrag.embedding.base.NullEmbeddingCache` \{#agrag-embedding-base-NullEmbeddingCache}

Bases: <code>[EmbeddingCache](EmbeddingCache.md)</code>

A cache that never stores anything. The default when none is injected.

**Functions:**

- [**get**](#agrag-embedding-base-NullEmbeddingCache-get) – Always miss.
- [**set**](#agrag-embedding-base-NullEmbeddingCache-set) – Do nothing.

## `get` \{#agrag-embedding-base-NullEmbeddingCache-get}

```python
get(*, text:str, model:str, normalize:bool) -> list[float] | None
```

Always miss.

## `set` \{#agrag-embedding-base-NullEmbeddingCache-set}

```python
set(*, text:str, model:str, normalize:bool, vector:list[float]) -> None
```

Do nothing.
