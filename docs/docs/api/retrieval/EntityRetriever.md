---
title: agrag.retrieval.EntityRetriever
sidebar_label: EntityRetriever
---

# `agrag.retrieval.EntityRetriever` \{#agrag-retrieval-EntityRetriever}

```python
EntityRetriever(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None, entity_labels:Sequence[str] | None = None, tracer:Tracer | None = None) -> None
```

Bases: <code>[Retriever](retrievers/base/Retriever.md)</code>

Dense entity search via vector similarity.

Embeds the query, searches via the GraphStore-native or
VectorStore path, then loads every hit from the graph. A hit that
no longer exists in the graph is dropped.

The native path searches one vector index per entity label, so it
needs the labels ingestion provisioned indexes for: the label
filter when the caller sets one, otherwise `entity_labels`.

**Functions:**

- [**retrieve**](#agrag-retrieval-EntityRetriever-retrieve) – Run entity search and return loaded results.

**Attributes:**

- [**name**](#agrag-retrieval-EntityRetriever-name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](../graphdb/base/GraphStore.md)</code>) – Backs entity search when vector_store is
  absent.
- **embedder** (<code>[Embedder](../embedding/base/Embedder.md)</code>) – Produces query vectors.
- **vector_store** (<code>[VectorStore](../vectordb/base/VectorStore.md) | None</code>) – Optional VectorStore for hybrid search.
- **settings** (<code>[RetrievalSettings](settings/RetrievalSettings.md) | None</code>) – Retrieval configuration; defaults from
  environment.
- **entity_labels** (<code>Sequence\[str\] | None</code>) – The schema entity labels native search runs
  against. None uses settings.entity_labels.
- **tracer** (<code>Tracer | None</code>) – Opens the retriever and its children's spans. None
  opens no recorded span.

## `name` \{#agrag-retrieval-EntityRetriever-name}

```python
name = 'entity'
```

## `retrieve` \{#agrag-retrieval-EntityRetriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int | None = None) -> list[SearchResult]
```

Run entity search and return loaded results.

**Parameters:**

- **query** (<code>str</code>) – The natural-language query text.
- **filters** (<code>[SearchFilters](filters/SearchFilters.md) | None</code>) – Constraints applied to the search.
- **limit** (<code>int | None</code>) – Maximum results. None uses settings.entity_top_k.
  Zero or negative returns no results without searching.

**Returns:**

- <code>list\[[SearchResult](../common/data_models/search_result/SearchResult.md)\]</code> – Ranked SearchResults with resolved entity ids. The list is
  empty when the limit is not positive, or when the search ran and
  found nothing.

**Raises:**

- <code>ValueError</code> – Native search was selected and neither the
  filter nor the configuration names an entity label, or a
  stored entity node cannot be parsed.
- <code>Exception</code> – Any embedding, vector search, or graph read
  failure propagates, so a failed search is not mistaken
  for an empty one.
