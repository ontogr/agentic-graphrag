---
title: agrag.embedding.fastembed_dense.FastEmbedEmbedder
sidebar_label: FastEmbedEmbedder
---

# `agrag.embedding.fastembed_dense.FastEmbedEmbedder` \{#agrag-embedding-fastembed_dense-FastEmbedEmbedder}

```python
FastEmbedEmbedder(*, settings:EmbeddingSettings | None = None, cache:EmbeddingCache | None = None, model:object | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Embedder](../base/Embedder.md)</code>

A dense embedder built on FastEmbed, which runs ONNX models on the CPU.

The model loads lazily on the first `embed` or `dimensions` call, so
constructing the embedder does not download weights. Each blocking call
into FastEmbed runs in a worker thread, which keeps the event loop free
for other work while a large batch encodes.

**Functions:**

- [**dimensions**](#agrag-embedding-fastembed_dense-FastEmbedEmbedder-dimensions) – Return the dimension the loaded model produces.
- [**embed**](#agrag-embedding-fastembed_dense-FastEmbedEmbedder-embed) – Embed a batch of texts, using the cache where possible.
- [**embed_one**](#agrag-embedding-fastembed_dense-FastEmbedEmbedder-embed_one) – Embed a single text.

**Attributes:**

- [**distance**](#agrag-embedding-fastembed_dense-FastEmbedEmbedder-distance) (<code>[Distance](../../common/data_models/vector_record/Distance.md)</code>) – Return the distance metric for vector indexes created for this embedder.
- [**model**](#agrag-embedding-fastembed_dense-FastEmbedEmbedder-model) (<code>str</code>) – The configured model name.

**Parameters:**

- **settings** (<code>[EmbeddingSettings](../settings/EmbeddingSettings.md) | None</code>) – Embedder configuration. Defaults to `EmbeddingSettings()`.
  FastEmbed ignores `device`.
- **cache** (<code>[EmbeddingCache](../base/EmbeddingCache.md) | None</code>) – An optional content-addressed cache. Defaults to a no-op cache.
- **model** (<code>object | None</code>) – A pre-built FastEmbed `TextEmbedding`, for tests. When set,
  `embed` calls this object instead of building one.
- **tracer** (<code>Tracer | None</code>) – Opens every span this embedder's methods produce.

## `dimensions` \{#agrag-embedding-fastembed_dense-FastEmbedEmbedder-dimensions}

```python
dimensions() -> int
```

Return the dimension the loaded model produces.

Calling this loads the model the first time, through the same locked
worker-thread path `embed` uses, so it is safe to call concurrently
with `embed`.

**Returns:**

- <code>int</code> – The dimension of the vectors the loaded model produces.

## `distance` \{#agrag-embedding-fastembed_dense-FastEmbedEmbedder-distance}

```python
distance: Distance
```

Return the distance metric for vector indexes created for this embedder.

Defaults to cosine, which matches normalized sentence-transformer models.
Concrete embedders can override when their vectors use a different
metric.

## `embed` \{#agrag-embedding-fastembed_dense-FastEmbedEmbedder-embed}

```python
embed(texts:Sequence[str]) -> list[list[float]]
```

Embed a batch of texts, using the cache where possible.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The texts to embed, in order.

**Returns:**

- <code>list\[list\[float\]\]</code> – One vector per input text, in the same order.

## `embed_one` \{#agrag-embedding-fastembed_dense-FastEmbedEmbedder-embed_one}

```python
embed_one(text:str) -> list[float]
```

Embed a single text.

**Parameters:**

- **text** (<code>str</code>) – The text to embed.

**Returns:**

- <code>list\[float\]</code> – The text's embedding vector.

## `model` \{#agrag-embedding-fastembed_dense-FastEmbedEmbedder-model}

```python
model: str
```

The configured model name.

**Returns:**

- <code>str</code> – The model name from the embedder settings.
