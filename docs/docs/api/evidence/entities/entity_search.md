---
title: agrag.evidence.entities.entity_search
sidebar_label: entity_search
---

# `agrag.evidence.entities.entity_search` \{#agrag-evidence-entities-entity_search}

```python
entity_search(store:GraphStore, embedder:Embedder, query:str, *, scope:frozenset[str], labels:Sequence[str] | None = None, limit:int, mode:DiscoveryMode = DiscoveryMode.HYBRID, support_limit:int = 3) -> EntityResult
```

Find up to `limit` entities that match a query by name or by meaning.

The lexical leg matches the words of the query against the `name` of each
entity. The semantic leg embeds the query and searches the `embedding` of
each entity. The hybrid mode runs both and fuses the rankings with reciprocal
rank fusion. Each label needs a full-text index on `name` and a vector index
on `embedding`. A missing or offline index gives `index_not_ready`.

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
- **labels** (<code>Sequence\[str\] | None</code>) – The entity labels to search. None searches every entity label that
  has a vector index, which is every label the graph schema declares.
- **limit** (<code>int</code>) – The most entities to return. Must be positive.
- **mode** (<code>[DiscoveryMode](../../common/data_models/evidence/DiscoveryMode.md)</code>) – Which legs to run.
- **support_limit** (<code>int</code>) – The most supporting passages listed for each entity. Must
  be positive.

**Returns:**

- <code>[EntityResult](../../common/data_models/entity_search/EntityResult.md)</code> – The entities, best first, with the status and the index state.

**Raises:**

- <code>ValueError</code> – `limit` or `support_limit` is not positive.
