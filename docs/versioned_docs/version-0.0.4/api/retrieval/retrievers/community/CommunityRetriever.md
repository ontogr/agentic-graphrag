---
title: agrag.retrieval.retrievers.community.CommunityRetriever
sidebar_label: CommunityRetriever
---

# `agrag.retrieval.retrievers.community.CommunityRetriever` \{#agrag-retrieval-retrievers-community-CommunityRetriever}

```python
CommunityRetriever(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Retriever](../base/Retriever.md)</code>

Dense search over community reports, for direct thematic questions.

**Functions:**

- [**retrieve**](#agrag-retrieval-retrievers-community-CommunityRetriever-retrieve) – Run community-report search and return hydrated results.

**Attributes:**

- [**name**](#agrag-retrieval-retrievers-community-CommunityRetriever-name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](../../../graphdb/base/GraphStore.md)</code>) – Where community nodes live.
- **embedder** (<code>[Embedder](../../../embedding/base/Embedder.md)</code>) – Produces query vectors.
- **vector_store** (<code>[VectorStore](../../../vectordb/base/VectorStore.md) | None</code>) – Optional VectorStore for hybrid search.
- **settings** (<code>[RetrievalSettings](../../settings/RetrievalSettings.md) | None</code>) – Retrieval configuration; defaults from environment.
- **tracer** (<code>Tracer | None</code>) – Opens the retriever and its children's spans. None
  opens no recorded span.

## `name` \{#agrag-retrieval-retrievers-community-CommunityRetriever-name}

```python
name = 'community'
```

## `retrieve` \{#agrag-retrieval-retrievers-community-CommunityRetriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int | None = None) -> list[SearchResult]
```

Run community-report search and return hydrated results.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text.
- **filters** (<code>[SearchFilters](../../filters/SearchFilters.md) | None</code>) – Constraints applied to the search.
- **limit** (<code>int | None</code>) – Maximum results. None uses settings.community_top_k.
  Zero or negative returns no results without searching.
