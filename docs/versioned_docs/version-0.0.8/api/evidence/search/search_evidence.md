---
title: agrag.evidence.search.search_evidence
sidebar_label: search_evidence
---

# `agrag.evidence.search.search_evidence` \{#agrag-evidence-search-search_evidence}

```python
search_evidence(store:GraphStore, embedder:Embedder, query:str, *, mode:EvidenceSearchMode = EvidenceSearchMode.HYBRID, limit:int = DEFAULT_SEARCH_LIMIT, scope:frozenset[str], vector_store:VectorStore | None = None, reranker:Reranker | None = None, settings:RetrievalSettings | None = None, timeout:float | None = None) -> EvidenceSearchResult
```

Find up to `limit` visible passages that match a query.

The lexical leg matches the words of the query against chunk text. The
semantic leg embeds the query and searches the chunk embeddings. The hybrid
mode runs both and fuses them, or delegates fusion to an external store.
Hybrid mode with a reranker reorders the top fused hits with the
cross-encoder, and lexical and semantic modes never rerank. Search returns
status `index_not_ready` when a needed index or external collection is
missing. It returns `empty_scope` without searching when `scope` is
empty.

**Parameters:**

- **store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – The graph store to search.
- **embedder** (<code>[Embedder](../../embedding/base/Embedder.md)</code>) – Embeds the query for the semantic leg. The lexical leg does not
  use it.
- **query** (<code>str</code>) – The query text. Lucene syntax is not applied: each word is
  searched as a plain term.
- **mode** (<code>[EvidenceSearchMode](../../common/data_models/evidence/EvidenceSearchMode.md)</code>) – Which legs to run.
- **limit** (<code>int</code>) – The most hits to return. Must be positive.
- **scope** (<code>frozenset\[str\]</code>) – Keys of the documents that may be searched.
- **vector_store** (<code>[VectorStore](../../vectordb/base/VectorStore.md) | None</code>) – Optional external vector store. Placement is not validated
  by this function.
- **reranker** (<code>[Reranker](../rerank/Reranker.md) | None</code>) – Scores passage texts against the query to reorder the top
  fused hits of hybrid mode. None runs hybrid search without rerank.
- **settings** (<code>[RetrievalSettings](../../retrieval/settings/RetrievalSettings.md) | None</code>) – Fusion and rerank configuration. None uses the defaults.
- **timeout** (<code>float | None</code>) – Server-side transaction timeout in seconds for each store read.
  None uses the server's default.

**Returns:**

- <code>[EvidenceSearchResult](../../common/data_models/evidence/EvidenceSearchResult.md)</code> – The hits, best first, with the status, truncation flag, index state and
- <code>[EvidenceSearchResult](../../common/data_models/evidence/EvidenceSearchResult.md)</code> – any failed legs. A failed rerank stage is recorded in the failures and
- <code>[EvidenceSearchResult](../../common/data_models/evidence/EvidenceSearchResult.md)</code> – leaves the status and the fused order unchanged.

**Raises:**

- <code>ValueError</code> – `limit` is not positive.
