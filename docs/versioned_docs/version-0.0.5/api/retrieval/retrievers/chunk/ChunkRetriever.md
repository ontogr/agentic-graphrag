---
title: agrag.retrieval.retrievers.chunk.ChunkRetriever
sidebar_label: ChunkRetriever
---

# `agrag.retrieval.retrievers.chunk.ChunkRetriever` \{#agrag-retrieval-retrievers-chunk-ChunkRetriever}

```python
ChunkRetriever(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Retriever](../base/Retriever.md)</code>

Dense chunk search via vector similarity.

Embeds the query, searches via the GraphStore-native or VectorStore
path, then loads each hit into a Chunk. The native
path searches the `Chunk` vector index ingestion provisions; the
VectorStore path searches `chunk_collection`.

**Functions:**

- [**retrieve**](#agrag-retrieval-retrievers-chunk-ChunkRetriever-retrieve) – Run chunk search and return loaded results.

**Attributes:**

- [**name**](#agrag-retrieval-retrievers-chunk-ChunkRetriever-name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](../../../graphdb/base/GraphStore.md)</code>) – Backs chunk search when vector_store is
  absent.
- **embedder** (<code>[Embedder](../../../embedding/base/Embedder.md)</code>) – Produces query vectors.
- **vector_store** (<code>[VectorStore](../../../vectordb/base/VectorStore.md) | None</code>) – Optional VectorStore for hybrid search.
- **settings** (<code>[RetrievalSettings](../../settings/RetrievalSettings.md) | None</code>) – Retrieval configuration. Defaults from
  environment.
- **tracer** (<code>Tracer | None</code>) – Opens spans for the retriever and its children. None
  opens no recorded span.

## `name` \{#agrag-retrieval-retrievers-chunk-ChunkRetriever-name}

```python
name = 'chunk'
```

## `retrieve` \{#agrag-retrieval-retrievers-chunk-ChunkRetriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int | None = None) -> list[SearchResult]
```

Run chunk search and return loaded results.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text.
- **filters** (<code>[SearchFilters](../../filters/SearchFilters.md) | None</code>) – Constraints applied to the search.
- **limit** (<code>int | None</code>) – Maximum results. None uses settings.chunk_top_k.
  Zero or negative returns no results without searching.

**Returns:**

- <code>list\[[SearchResult](../../../common/data_models/search_result/SearchResult.md)\]</code> – Ranked SearchResults with loaded Chunk items. The list is empty when
  the limit is not positive, or when the search ran and found
  nothing.

**Raises:**

- <code>Exception</code> – Any embedding, vector search, or graph read
  failure propagates, so a failed search is not mistaken
  for an empty one.
