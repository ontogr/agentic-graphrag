---
title: agrag.evidence
sidebar_position: 13
---


# `agrag.evidence` \{#agrag-evidence}

Evidence discovery, exact fetch, navigation, entity search and citation checks.

The functions take a graph store and enforce the caller's document scope inside
their queries. Evidence ids name passage text of one version of a document.

**Modules:**

- [**citation**](citation/index.md) – Check that cited evidence ids trace to evidence the caller fetched.
- [**discover**](discover/index.md) – Find visible passages by full-text search, vector search, or both.
- [**entities**](entities/index.md) – Find entities by name or meaning, and explore typed relations around one entity.
- [**fetch**](fetch/index.md) – Fetch the exact text behind evidence ids, limited to the caller's scope.
- [**ids**](ids/index.md) – Encode and decode evidence ids.
- [**navigate**](navigate/index.md) – Navigate from one evidence passage to its neighbors, within scope and bounds.
- [**source_status**](source_status/index.md) – Read the committed lifecycle and index state of a document source.

**Functions:**

- [**check_citations**](citation/check_citations.md) – Return one verdict for each cited evidence id, in the order given.
- [**explore**](entities/explore.md) – Explore the entity relations around one entity, within bounds.
- [**find_entities**](entities/find_entities.md) – Find up to `limit` entities that match a query by name or by meaning.
