---
title: agrag.embedding
sidebar_position: 5
---


# `agrag.embedding` \{#agrag-embedding}

Text embedding: turn strings into dense vectors.

**Modules:**

- [**base**](base/index.md) – The Embedder and EmbeddingCache protocols.
- [**errors**](errors/index.md) – Errors that the embedding layer raises.
- [**fastembed_bm25**](fastembed_bm25/index.md) – BM25 sparse embedder backed by FastEmbed.
- [**sentence_transformers**](sentence_transformers/index.md) – Sentence-transformers embedder implementation.
- [**settings**](settings/index.md) – Settings for the sentence-transformers embedder.
- [**sparse_base**](sparse_base/index.md) – Sparse lexical vectors and the sparse embedder protocol.

**Classes:**

- [**Embedder**](base/Embedder.md) – A component that turns text into dense embedding vectors.
- [**EmbeddingSettings**](settings/EmbeddingSettings.md) – Sentence-transformers embedder configuration.
- [**FastEmbedBM25Embedder**](fastembed_bm25/FastEmbedBM25Embedder.md) – A sparse BM25 embedder built on FastEmbed.
- [**SentenceTransformerEmbedder**](sentence_transformers/SentenceTransformerEmbedder.md) – An embedder backed by sentence-transformers.
- [**SparseEmbedder**](sparse_base/SparseEmbedder.md) – A component that turns text into sparse lexical vectors, for hybrid search.
- [**SparseVector**](sparse_base/SparseVector.md) – A sparse vector: nonzero indices and their values.

**Functions:**

- [**build_embedder**](build_embedder.md) – Build an embedder from a model name, or return an embedder unchanged.
