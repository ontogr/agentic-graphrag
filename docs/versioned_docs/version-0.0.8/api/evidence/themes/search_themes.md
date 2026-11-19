---
title: agrag.evidence.themes.search_themes
sidebar_label: search_themes
---

# `agrag.evidence.themes.search_themes` \{#agrag-evidence-themes-search_themes}

```python
search_themes(store:GraphStore, embedder:Embedder, query:str, *, scope:frozenset[str], limit:int = DEFAULT_THEME_LIMIT, support_limit:int = DEFAULT_SUPPORT_LIMIT, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None, timeout:float | None = None) -> ThemeResult
```

Find up to `limit` themes whose member passages match a query.

The query is embedded and searched against the community report embeddings
of the last detection run, so a theme matches by meaning only. Each theme is
returned with the visible in-scope passages that mention its member
entities, and a community with no such passage is dropped. Communities come
from the last `detect_communities` run: membership that has since become
hidden or out of scope is filtered out, so no such passage can appear, and
documents ingested after that run are absent until the next run.

**Parameters:**

- **store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – The graph store to search.
- **embedder** (<code>[Embedder](../../embedding/base/Embedder.md)</code>) – Embeds the query for the community vector search.
- **query** (<code>str</code>) – The query text.
- **scope** (<code>frozenset\[str\]</code>) – Keys of the documents whose passages may be used.
- **limit** (<code>int</code>) – The most themes to return. Must be positive.
- **support_limit** (<code>int</code>) – The most passages listed for each theme. Must be
  positive.
- **vector_store** (<code>[VectorStore](../../vectordb/base/VectorStore.md) | None</code>) – Optional external vector store holding the community
  embeddings. Placement is not validated by this function.
- **settings** (<code>[RetrievalSettings](../../retrieval/settings/RetrievalSettings.md) | None</code>) – Retrieval configuration. None uses the defaults. Theme search
  reads no rerank or fusion setting; the parameter keeps the call
  shape of the other retrieval tools.
- **timeout** (<code>float | None</code>) – Server-side transaction timeout in seconds for each store
  read. None uses the server's default.

**Returns:**

- <code>[ThemeResult](../../common/data_models/theme_search/ThemeResult.md)</code> – The themes, best first, with the status, truncation flag, index state
- <code>[ThemeResult](../../common/data_models/theme_search/ThemeResult.md)</code> – and any failed leg.

**Raises:**

- <code>ValueError</code> – `limit` or `support_limit` is not positive.
