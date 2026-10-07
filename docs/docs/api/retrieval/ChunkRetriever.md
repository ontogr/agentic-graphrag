---
title: agrag.retrieval.ChunkRetriever
sidebar_label: ChunkRetriever
---

# `agrag.retrieval.ChunkRetriever` \{#agrag-retrieval-ChunkRetriever}

```python
ChunkRetriever(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Retriever](retrievers/base/Retriever.md)</code>

Dense chunk search via vector similarity.

Embeds the query, searches via the GraphStore-native or VectorStore
path, then loads each hit into a Chunk. The native
path searches the `Chunk` vector index ingestion provisions; the
VectorStore path searches `chunk_collection`.

**Functions:**

- [**retrieve**](#agrag-retrieval-ChunkRetriever-retrieve) – Run chunk search and return loaded results.

**Attributes:**

- [**name**](#agrag-retrieval-ChunkRetriever-name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](../graphdb/base/GraphStore.md)</code>) – Backs chunk search when vector_store is
  absent.
- **embedder** (<code>[Embedder](../embedding/base/Embedder.md)</code>) – Produces query vectors.
- **vector_store** (<code>[VectorStore](../vectordb/base/VectorStore.md) | None</code>) – Optional VectorStore for hybrid search.
- **settings** (<code>[RetrievalSettings](settings/RetrievalSettings.md) | None</code>) – Retrieval configuration; defaults from
  environment.
- **tracer** (<code>Tracer | None</code>) – Opens the retriever and its children's spans. None
  opens no recorded span.

## `name` \{#agrag-retrieval-ChunkRetriever-name}

```python
name = 'chunk'
```

## `retrieve` \{#agrag-retrieval-ChunkRetriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int | None = None) -> list[SearchResult]
```

Run chunk search and return loaded results.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text.
- **filters** (<code>[SearchFilters](filters/SearchFilters.md) | None</code>) – Constraints applied to the search.
- **limit** (<code>int | None</code>) – Maximum results. None uses settings.chunk_top_k.
  Zero or negative returns no results without searching.

**Returns:**

- <code>list\[[SearchResult](../common/data_models/search_result/SearchResult.md)\]</code> – Ranked SearchResults with loaded Chunk items. A child chunk result
- <code>list\[[SearchResult](../common/data_models/search_result/SearchResult.md)\]</code> – carries its parent chunk in `SearchResult.parent`. The list is
- <code>list\[[SearchResult](../common/data_models/search_result/SearchResult.md)\]</code> – empty when the limit is not positive, or when the search ran
- <code>list\[[SearchResult](../common/data_models/search_result/SearchResult.md)\]</code> – and found nothing.

**Raises:**

- <code>Exception</code> – Any embedding, vector search, or graph read
  failure propagates, so a failed search is not mistaken
  for an empty one.
