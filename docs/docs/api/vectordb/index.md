---
title: agrag.vectordb
sidebar_position: 12
---


# `agrag.vectordb` \{#agrag-vectordb}

Vector storage backends and the build shortcut.

**Modules:**

- [**base**](base/index.md) – The VectorStore abstraction and its build shortcut.
- [**errors**](errors/index.md) – Errors that the vector-store layer raises.
- [**milvus**](milvus/index.md) – Milvus vector-store backend.
- [**pending**](pending/index.md) – Pending-record bookkeeping shared by the VectorStore adapters.
- [**qdrant**](qdrant/index.md) – Qdrant vector-store backend.
- [**settings**](settings/index.md) – Settings for vector-store backends.
- [**weaviate**](weaviate/index.md) – Weaviate vector-store backend.

**Classes:**

- [**CollectionDimensionMismatchError**](errors/CollectionDimensionMismatchError.md) – A collection already exists with a different embedding dimension.
- [**MilvusSettings**](settings/MilvusSettings.md) – Milvus connection configuration.
- [**MilvusVectorStore**](milvus/MilvusVectorStore.md) – A `VectorStore` backed by Milvus, including native hybrid search.
- [**QdrantSettings**](settings/QdrantSettings.md) – Qdrant connection configuration.
- [**QdrantVectorStore**](qdrant/QdrantVectorStore.md) – A `VectorStore` backed by Qdrant, including native hybrid search.
- [**VectorStore**](base/VectorStore.md) – A vector database backend: collection lifecycle, writes, and search.
- [**VectorStoreError**](errors/VectorStoreError.md) – The base class for every vector-store error.
- [**VectorStoreMissingExtraError**](errors/VectorStoreMissingExtraError.md) – A vector store exists, but its package extra is not installed.
- [**WeaviateSettings**](settings/WeaviateSettings.md) – Weaviate connection configuration.
- [**WeaviateVectorStore**](weaviate/WeaviateVectorStore.md) – A `VectorStore` backed by Weaviate, including native hybrid search.

**Functions:**

- [**build_vector_store**](build_vector_store.md) – Build a vector store from a backend name, or return one unchanged.
