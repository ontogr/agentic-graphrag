---
title: agrag.embedding.cached.CachedEmbedder
sidebar_label: CachedEmbedder
---

# `agrag.embedding.cached.CachedEmbedder` \{#agrag-embedding-cached-CachedEmbedder}

```python
CachedEmbedder(inner:Embedder, *, maxsize:int = 256) -> None
```

Bases: <code>[Embedder](../base/Embedder.md)</code>

An `Embedder` that caches query vectors and deduplicates in-flight calls.

Wraps another embedder with an in-memory LRU keyed by text, so repeated
queries (for example the same query hitting two search tools in one
turn) embed once. Texts that are cached or already being embedded by an
earlier call are not sent to the inner embedder; the remaining texts go
in one batch call. A failed inner call resolves its in-flight futures
with the error and is retried on the next call. Cached vectors are
stored and returned as copies, so callers cannot mutate them.

**Functions:**

- [**dimensions**](#agrag-embedding-cached-CachedEmbedder-dimensions) – Return the wrapped embedder's dimension, cached after the first call.
- [**embed**](#agrag-embedding-cached-CachedEmbedder-embed) – Embed a batch of texts, using the cache and in-flight sharing.
- [**embed_one**](#agrag-embedding-cached-CachedEmbedder-embed_one) – Embed a single text.

**Attributes:**

- [**distance**](#agrag-embedding-cached-CachedEmbedder-distance) (<code>[Distance](../../common/data_models/vector_record/Distance.md)</code>) – The wrapped embedder's distance metric.
- [**model**](#agrag-embedding-cached-CachedEmbedder-model) (<code>str</code>) – The wrapped embedder's model name.

**Parameters:**

- **inner** (<code>[Embedder](../base/Embedder.md)</code>) – The embedder that performs the actual embedding.
- **maxsize** (<code>int</code>) – The most vectors the LRU cache holds. The least
  recently used entry is evicted beyond this.

## `dimensions` \{#agrag-embedding-cached-CachedEmbedder-dimensions}

```python
dimensions() -> int
```

Return the wrapped embedder's dimension, cached after the first call.

**Returns:**

- <code>int</code> – The dimension of the vectors the wrapped embedder produces.

## `distance` \{#agrag-embedding-cached-CachedEmbedder-distance}

```python
distance: Distance
```

The wrapped embedder's distance metric.

## `embed` \{#agrag-embedding-cached-CachedEmbedder-embed}

```python
embed(texts:Sequence[str]) -> list[list[float]]
```

Embed a batch of texts, using the cache and in-flight sharing.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The texts to embed, in order. Duplicates are embedded
  once.

**Returns:**

- <code>list\[list\[float\]\]</code> – One vector per input text, in the same order. Vector values are
- <code>list\[list\[float\]\]</code> – fresh copies; mutating a returned vector never changes the
- <code>list\[list\[float\]\]</code> – cache.

## `embed_one` \{#agrag-embedding-cached-CachedEmbedder-embed_one}

```python
embed_one(text:str) -> list[float]
```

Embed a single text.

**Parameters:**

- **text** (<code>str</code>) – The text to embed.

**Returns:**

- <code>list\[float\]</code> – The text's embedding vector.

## `model` \{#agrag-embedding-cached-CachedEmbedder-model}

```python
model: str
```

The wrapped embedder's model name.
