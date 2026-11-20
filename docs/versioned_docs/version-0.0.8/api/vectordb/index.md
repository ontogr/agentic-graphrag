---
title: agrag.vectordb
sidebar_position: 17
---


# `agrag.vectordb` \{#agrag-vectordb}

External vector indexes with graph-owned visibility and placement.

**Modules:**

- [**base**](base/index.md) – The asynchronous contract for an exclusive external vector index.
- [**errors**](errors/index.md) – Errors exposed by external vector indexes.
- [**kinds**](kinds/index.md) – Map public graph labels to external collection kinds.
- [**milvus**](milvus/index.md) – Milvus dense and native BM25 indexes for external vector placement.
- [**placement**](placement/index.md) – Validate that a graph continues to use its original vector placement.
- [**qdrant**](qdrant/index.md) – Qdrant indexes with dense vectors and locally computed BM25 sparse vectors.
- [**settings**](settings/index.md) – Validation shared by external vector store settings.
- [**weaviate**](weaviate/index.md) – Weaviate collections with self-provided vectors and native BM25 fusion.

**Classes:**

- [**CollectionMismatchError**](errors/CollectionMismatchError.md) – An existing collection has incompatible dimensions or distance.
- [**MilvusSettings**](milvus/MilvusSettings.md) – Milvus or Zilliz Cloud connection and collection namespace.
- [**MilvusVectorStore**](milvus/MilvusVectorStore.md) – Store UUID-keyed vectors with server-generated BM25 sparse vectors.
- [**QdrantSettings**](qdrant/QdrantSettings.md) – Qdrant connection and per-graph collection names.
- [**QdrantVectorStore**](qdrant/QdrantVectorStore.md) – An exclusive vector index on Qdrant 1.17 or newer.
- [**VectorPlacementError**](errors/VectorPlacementError.md) – The requested vector placement disagrees with the graph's recorded placement.
- [**VectorStore**](base/VectorStore.md) – An external index whose hits must be joined to visible graph nodes.
- [**VectorStoreError**](errors/VectorStoreError.md) – An external vector index operation failed.
- [**VectorStoreMissingExtraError**](errors/VectorStoreMissingExtraError.md) – The selected vector store's optional client is not installed.
- [**WeaviateSettings**](weaviate/WeaviateSettings.md) – Weaviate connection and collection isolation settings.
- [**WeaviateVectorStore**](weaviate/WeaviateVectorStore.md) – An exclusive external index backed by Weaviate.

**Functions:**

- [**build_vector_store**](build_vector_store.md) – Construct a named vector index or return an existing instance unchanged.
- [**validate_placement**](placement/validate_placement.md) – Compare placement, creating it on first open only when write is true.

**Attributes:**

- [**VectorStoreName**](VectorStoreName.md) –
