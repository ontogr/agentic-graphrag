---
title: agrag.retrieval.CommunityRetriever
sidebar_label: CommunityRetriever
---

# `agrag.retrieval.CommunityRetriever` \{#agrag-retrieval-CommunityRetriever}

```python
CommunityRetriever(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Retriever](retrievers/base/Retriever.md)</code>

Dense search over community reports, for direct thematic questions.

**Functions:**

- [**retrieve**](#agrag-retrieval-CommunityRetriever-retrieve) – Run community-report search and return loaded results.

**Attributes:**

- [**name**](#agrag-retrieval-CommunityRetriever-name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](../graphdb/base/GraphStore.md)</code>) – Where community nodes live.
- **embedder** (<code>[Embedder](../embedding/base/Embedder.md)</code>) – Produces query vectors.
- **vector_store** (<code>[VectorStore](../vectordb/base/VectorStore.md) | None</code>) – Optional VectorStore for hybrid search.
- **settings** (<code>[RetrievalSettings](settings/RetrievalSettings.md) | None</code>) – Retrieval configuration; defaults from environment.
- **tracer** (<code>Tracer | None</code>) – Opens the retriever and its children's spans. None
  opens no recorded span.

## `name` \{#agrag-retrieval-CommunityRetriever-name}

```python
name = 'community'
```

## `retrieve` \{#agrag-retrieval-CommunityRetriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int | None = None) -> list[SearchResult]
```

Run community-report search and return loaded results.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text.
- **filters** (<code>[SearchFilters](filters/SearchFilters.md) | None</code>) – Constraints applied to the search.
- **limit** (<code>int | None</code>) – Maximum results. None uses settings.community_top_k.
  Zero or negative returns no results without searching.

**Returns:**

- <code>list\[[SearchResult](../common/data_models/search_result/SearchResult.md)\]</code> – Ranked SearchResults with loaded Community items. The list is
  empty when the limit is not positive, or when the search ran and
  found nothing.

**Raises:**

- <code>Exception</code> – Any embedding, vector search, or graph read
  failure propagates, so a failed search is not mistaken
  for an empty one.
