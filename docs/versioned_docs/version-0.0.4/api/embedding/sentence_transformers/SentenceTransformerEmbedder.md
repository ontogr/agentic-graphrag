---
title: agrag.embedding.sentence_transformers.SentenceTransformerEmbedder
sidebar_label: SentenceTransformerEmbedder
---

# `agrag.embedding.sentence_transformers.SentenceTransformerEmbedder` \{#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder}

```python
SentenceTransformerEmbedder(*, settings:EmbeddingSettings | None = None, cache:EmbeddingCache | None = None, model:object | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Embedder](../base/Embedder.md)</code>

An embedder backed by sentence-transformers.

The model loads lazily on first `embed`, so constructing the embedder
does not touch the GPU or download weights. Every blocking call into the
model runs in a worker thread (`asyncio.to_thread`), so the event loop
stays free for other work while a large batch encodes.

**Functions:**

- [**dimensions**](#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-dimensions) – Return the dimension the loaded model produces.
- [**embed**](#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-embed) – Embed a batch of texts, using the cache where possible.
- [**embed_one**](#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-embed_one) – Embed a single text.

**Attributes:**

- [**distance**](#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-distance) (<code>[Distance](../../common/data_models/vector_record/Distance.md)</code>) – Return the distance metric for vector indexes created for this embedder.
- [**model**](#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-model) (<code>str</code>) – The configured model name.

**Parameters:**

- **settings** (<code>[EmbeddingSettings](../settings/EmbeddingSettings.md) | None</code>) – Embedder configuration. Defaults to `EmbeddingSettings()`.
- **cache** (<code>[EmbeddingCache](../base/EmbeddingCache.md) | None</code>) – An optional content-addressed cache. Defaults to a no-op cache.
- **model** (<code>object | None</code>) – A pre-built sentence-transformers model, for tests. When set,
  `__init__` imports nothing and `embed` calls this object
  directly instead of building one.
- **tracer** (<code>Tracer | None</code>) – Opens every span this embedder's methods produce.

## `dimensions` \{#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-dimensions}

```python
dimensions() -> int
```

Return the dimension the loaded model produces.

Calling this loads the model the first time, the same
lock-protected, worker-thread path `embed` uses, so it is safe to
call concurrently with `embed` without stalling the event loop or
loading a second copy of the model.

**Raises:**

- <code>[EmbeddingMissingExtraError](../errors/EmbeddingMissingExtraError.md)</code> – sentence-transformers is not installed.

## `distance` \{#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-distance}

```python
distance: Distance
```

Return the distance metric for vector indexes created for this embedder.

Defaults to cosine, which matches normalized sentence-transformer models.
Concrete embedders may override when their vectors use a different
metric.

## `embed` \{#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-embed}

```python
embed(texts:Sequence[str]) -> list[list[float]]
```

Embed a batch of texts, using the cache where possible.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The texts to embed, in order.

**Returns:**

- <code>list\[list\[float\]\]</code> – One vector per input text, in the same order.

## `embed_one` \{#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-embed_one}

```python
embed_one(text:str) -> list[float]
```

Embed a single text.

**Parameters:**

- **text** (<code>str</code>) – The text to embed.

**Returns:**

- <code>list\[float\]</code> – The text's embedding vector.

## `model` \{#agrag-embedding-sentence_transformers-SentenceTransformerEmbedder-model}

```python
model: str
```

The configured model name.
