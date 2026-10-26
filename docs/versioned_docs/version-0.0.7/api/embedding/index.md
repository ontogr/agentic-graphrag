---
title: agrag.embedding
sidebar_position: 5
---


# `agrag.embedding` \{#agrag-embedding}

Text embedding: turn strings into dense vectors.

**Modules:**

- [**base**](base/index.md) – The Embedder and EmbeddingCache protocols.
- [**cached**](cached/index.md) – Embedder wrapper that caches query vectors in memory.
- [**errors**](errors/index.md) – Errors that the embedding layer raises.
- [**fastembed_dense**](fastembed_dense/index.md) – Dense embedder backed by FastEmbed and ONNX Runtime.
- [**sentence_transformers**](sentence_transformers/index.md) – Sentence-transformers embedder implementation.
- [**settings**](settings/index.md) – Settings for the dense embedders.

**Classes:**

- [**CachedEmbedder**](cached/CachedEmbedder.md) – An `Embedder` that caches query vectors and deduplicates in-flight calls.
- [**Embedder**](base/Embedder.md) – A component that turns text into dense embedding vectors.
- [**EmbeddingSettings**](settings/EmbeddingSettings.md) – Configuration shared by the FastEmbed and sentence-transformers embedders.
- [**FastEmbedEmbedder**](fastembed_dense/FastEmbedEmbedder.md) – A dense embedder built on FastEmbed, which runs ONNX models on the CPU.
- [**SentenceTransformerEmbedder**](sentence_transformers/SentenceTransformerEmbedder.md) – An embedder backed by sentence-transformers.

**Functions:**

- [**build_embedder**](build_embedder.md) – Build an embedder from a model name, or return an embedder unchanged.
