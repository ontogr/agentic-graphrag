---
title: agrag.embedding.SparseEmbedder
sidebar_label: SparseEmbedder
---

# `agrag.embedding.SparseEmbedder` \{#agrag-embedding-SparseEmbedder}

Bases: <code>ABC</code>

A component that turns text into sparse lexical vectors, for hybrid search.

**Functions:**

- [**embed**](#agrag-embedding-SparseEmbedder-embed) – Embed a batch of documents into sparse vectors.
- [**query_embed**](#agrag-embedding-SparseEmbedder-query_embed) – Embed a batch of search queries into sparse vectors.

**Attributes:**

- [**model**](#agrag-embedding-SparseEmbedder-model) (<code>str</code>) –

## `embed` \{#agrag-embedding-SparseEmbedder-embed}

```python
embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of documents into sparse vectors.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The document texts to embed, in order.

**Returns:**

- <code>list\[[SparseVector](sparse_base/SparseVector.md)\]</code> – One sparse vector per input text, in the same order.

## `model` \{#agrag-embedding-SparseEmbedder-model}

```python
model: str
```

## `query_embed` \{#agrag-embedding-SparseEmbedder-query_embed}

```python
query_embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of search queries into sparse vectors.

Query-side sparse embedding is not always the same computation as
document-side embedding: BM25, for example, applies term-frequency
and document-length normalization on the document side but only a
uniform per-term weight on the query side, since IDF weighting is
applied by the sparse index at query time instead. Implementations
with no such asymmetry may implement this identically to `embed`.

**Parameters:**

- **texts** (<code>Sequence\[str\]</code>) – The query texts to embed, in order.

**Returns:**

- <code>list\[[SparseVector](sparse_base/SparseVector.md)\]</code> – One sparse vector per input text, in the same order.
