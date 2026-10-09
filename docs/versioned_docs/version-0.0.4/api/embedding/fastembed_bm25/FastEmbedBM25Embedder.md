---
title: agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder
sidebar_label: FastEmbedBM25Embedder
---

# `agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder` \{#agrag-embedding-fastembed_bm25-FastEmbedBM25Embedder}

```python
FastEmbedBM25Embedder(*, model:str | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[SparseEmbedder](../sparse_base/SparseEmbedder.md)</code>

A sparse BM25 embedder built on FastEmbed.

The model loads lazily on first `embed`, so constructing the embedder
does not download weights. Each blocking call into FastEmbed runs in a
worker thread, keeping the event loop free. FastEmbed ships with the
`qdrant` extra, so a clean install without that extra raises
`EmbeddingMissingExtraError` rather than `ImportError`.

**Functions:**

- [**embed**](#agrag-embedding-fastembed_bm25-FastEmbedBM25Embedder-embed) – Embed a batch of documents into BM25 sparse vectors.
- [**query_embed**](#agrag-embedding-fastembed_bm25-FastEmbedBM25Embedder-query_embed) – Embed a batch of search queries into BM25 sparse vectors.

**Attributes:**

- [**model**](#agrag-embedding-fastembed_bm25-FastEmbedBM25Embedder-model) (<code>str</code>) – The configured model name, or the FastEmbed default when unset.

**Parameters:**

- **model** (<code>str | None</code>) – The FastEmbed BM25 model name. Defaults to FastEmbed's
  built-in BM25 model.
- **tracer** (<code>Tracer | None</code>) – Opens every span this embedder's methods produce.

## `embed` \{#agrag-embedding-fastembed_bm25-FastEmbedBM25Embedder-embed}

```python
embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of documents into BM25 sparse vectors.

Applies FastEmbed's document-side term-frequency and length
normalization weighting. Use `query_embed` for search queries.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The document texts to embed, in order.

**Returns:**

- <code>list\[[SparseVector](../sparse_base/SparseVector.md)\]</code> – One sparse vector per input text, in the same order.

## `model` \{#agrag-embedding-fastembed_bm25-FastEmbedBM25Embedder-model}

```python
model: str
```

The configured model name, or the FastEmbed default when unset.

## `query_embed` \{#agrag-embedding-fastembed_bm25-FastEmbedBM25Embedder-query_embed}

```python
query_embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of search queries into BM25 sparse vectors.

Uses FastEmbed's `query_embed`, which assigns each unique query
term a uniform weight of `1.0` rather than the document-side
term-frequency and length-normalization weighting `embed` applies;
IDF weighting is applied separately by the sparse index's
`Modifier.IDF` at query time.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The query texts to embed, in order.

**Returns:**

- <code>list\[[SparseVector](../sparse_base/SparseVector.md)\]</code> – One sparse vector per input text, in the same order.
