---
title: agrag.embedding.Embedder
sidebar_label: Embedder
---

# `agrag.embedding.Embedder` \{#agrag-embedding-Embedder}

Bases: <code>ABC</code>

A component that turns text into dense embedding vectors.

**Functions:**

- [**dimensions**](#agrag-embedding-Embedder-dimensions) – Return the dimension of the vectors this embedder produces.
- [**embed**](#agrag-embedding-Embedder-embed) – Embed a batch of texts.
- [**embed_one**](#agrag-embedding-Embedder-embed_one) – Embed a single text.

**Attributes:**

- [**distance**](#agrag-embedding-Embedder-distance) (<code>[Distance](../common/data_models/vector_record/Distance.md)</code>) – Return the distance metric for vector indexes created for this embedder.
- [**model**](#agrag-embedding-Embedder-model) (<code>str</code>) –

## `dimensions` \{#agrag-embedding-Embedder-dimensions}

```python
dimensions() -> int
```

Return the dimension of the vectors this embedder produces.

Async because a lazily-loaded embedder may need to load its model to
answer, and that load must go through the same worker-thread/lock
path `embed` uses rather than blocking the event loop.

## `distance` \{#agrag-embedding-Embedder-distance}

```python
distance: Distance
```

Return the distance metric for vector indexes created for this embedder.

Defaults to cosine, which matches normalized sentence-transformer models.
Concrete embedders may override when their vectors use a different
metric.

## `embed` \{#agrag-embedding-Embedder-embed}

```python
embed(texts:Sequence[str]) -> list[list[float]]
```

Embed a batch of texts.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The texts to embed, in order.

**Returns:**

- <code>list\[list\[float\]\]</code> – One vector per input text, in the same order.

## `embed_one` \{#agrag-embedding-Embedder-embed_one}

```python
embed_one(text:str) -> list[float]
```

Embed a single text.

**Parameters:**

- **text** (<code>str</code>) – The text to embed.

**Returns:**

- <code>list\[float\]</code> – The text's embedding vector.

## `model` \{#agrag-embedding-Embedder-model}

```python
model: str
```
