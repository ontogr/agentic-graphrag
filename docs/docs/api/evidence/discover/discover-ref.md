---
title: agrag.evidence.discover.discover
sidebar_label: discover
---

# `agrag.evidence.discover.discover` \{#agrag-evidence-discover-discover}

```python
discover(store:GraphStore, embedder:Embedder, query:str, *, mode:DiscoveryMode, limit:int, scope:frozenset[str]) -> DiscoveryResult
```

Find up to `limit` visible passages that match a query.

The lexical leg matches the words of the query against chunk text. The
semantic leg embeds the query and searches the chunk embeddings. The hybrid
mode runs both and fuses them. Discovery returns status `index_not_ready`
when a needed index is missing or not ONLINE. It returns `empty_scope`
without searching when `scope` is empty.

**Parameters:**

- **store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – The graph store to search.
- **embedder** (<code>[Embedder](../../embedding/base/Embedder.md)</code>) – Embeds the query for the semantic leg. The lexical leg does not
  use it.
- **query** (<code>str</code>) – The query text. Lucene syntax is not applied: each word is
  searched as a plain term.
- **mode** (<code>[DiscoveryMode](../../common/data_models/evidence/DiscoveryMode.md)</code>) – Which legs to run.
- **limit** (<code>int</code>) – The most hits to return. Must be positive.
- **scope** (<code>frozenset\[str\]</code>) – Keys of the documents that may be searched.

**Returns:**

- <code>[DiscoveryResult](../../common/data_models/evidence/DiscoveryResult.md)</code> – The hits, best first, with the status, truncation flag, index state and
- <code>[DiscoveryResult](../../common/data_models/evidence/DiscoveryResult.md)</code> – any failed legs.

**Raises:**

- <code>ValueError</code> – `limit` is not positive.
