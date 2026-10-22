---
title: agrag.evidence.entities.entity_search
sidebar_label: entity_search
---

# `agrag.evidence.entities.entity_search` \{#agrag-evidence-entities-entity_search}

```python
entity_search(store:GraphStore, embedder:Embedder, query:str, *, scope:frozenset[str], labels:Sequence[str] | None = None, limit:int, mode:EvidenceSearchMode = EvidenceSearchMode.HYBRID, support_limit:int = 3, vector_store:VectorStore | None = None) -> EntityResult
```

Find up to `limit` entities that match a query by name or by meaning.

The lexical leg matches the words of the query against the `name` of each
entity. The semantic leg embeds the query and searches the `embedding` of
each entity. The hybrid mode runs both and fuses the rankings with reciprocal
rank fusion, or delegates fusion to an external store. A missing or offline
index or vector collection gives `index_not_ready`.

An entity is returned only when a passage in `scope` mentions it. Its
`support` lists up to `support_limit` visible passages, as evidence ids.
An entity with passages in scope and no visible passage is returned with kind
`unsupported` and an empty support list.

**Parameters:**

- **store** (<code>[GraphStore](../../graphdb/base/GraphStore.md)</code>) – The graph store to search.
- **embedder** (<code>[Embedder](../../embedding/base/Embedder.md)</code>) – Embeds the query for the semantic leg. The lexical leg does not
  use it.
- **query** (<code>str</code>) – The query text. Lucene syntax is not applied: each word is searched
  as a plain term.
- **scope** (<code>frozenset\[str\]</code>) – Keys of the documents whose passages may be used.
- **labels** (<code>Sequence\[str\] | None</code>) – The entity labels to search. None discovers labels from graph
  indexes for native search, or entity name indexes for external search.
- **limit** (<code>int</code>) – The most entities to return. Must be positive.
- **mode** (<code>[EvidenceSearchMode](../../common/data_models/evidence/EvidenceSearchMode.md)</code>) – Which legs to run.
- **support_limit** (<code>int</code>) – The most supporting passages listed for each entity. Must
  be positive.
- **vector_store** (<code>VectorStore | None</code>) – Optional external vector store. Placement is not validated
  by this function.

**Returns:**

- <code>[EntityResult](../../common/data_models/entity_search/EntityResult.md)</code> – The entities, best first, with the status and the index state.

**Raises:**

- <code>ValueError</code> – `limit` or `support_limit` is not positive.
