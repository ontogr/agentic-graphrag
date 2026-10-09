---
title: agrag.retrieval.retrievers.base.Retriever
sidebar_label: Retriever
---

# `agrag.retrieval.retrievers.base.Retriever` \{#agrag-retrieval-retrievers-base-Retriever}

Bases: <code>ABC</code>

One retrieval method: given a query, return SearchResults.

Subclasses own exactly one strategy (dense entity search, chunk
search, BFS expansion). SearchEngine fans a query out to every
Retriever a Recipe names and hands the combined output to Fusion.

**Functions:**

- [**retrieve**](#agrag-retrieval-retrievers-base-Retriever-retrieve) – Run this retrieval method and return hydrated results.

**Attributes:**

- [**name**](#agrag-retrieval-retrievers-base-Retriever-name) (<code>str</code>) –

## `name` \{#agrag-retrieval-retrievers-base-Retriever-name}

```python
name: str
```

## `retrieve` \{#agrag-retrieval-retrievers-base-Retriever-retrieve}

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int = 10) -> list[SearchResult]
```

Run this retrieval method and return hydrated results.
