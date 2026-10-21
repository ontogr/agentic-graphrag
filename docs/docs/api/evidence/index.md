---
title: agrag.evidence
sidebar_position: 13
---


# `agrag.evidence` \{#agrag-evidence}

Evidence search, exact fetch, navigation, entity search and citation checks.

The functions take a graph store and enforce the caller's document scope inside
their queries. Evidence ids name passage text of one version of a document.

**Modules:**

- [**citation**](citation/index.md) – Check that cited evidence ids trace to evidence the caller fetched.
- [**entities**](entities/index.md) – Find entities by name or meaning, and explore typed relations around one entity.
- [**fetch**](fetch/index.md) – Fetch the exact text behind evidence ids, limited to the caller's scope.
- [**ids**](ids/index.md) – Encode and decode evidence ids.
- [**navigate**](navigate/index.md) – Navigate from one evidence passage to its neighbors, within scope and bounds.
- [**render**](render/index.md) – Render validated evidence citations without changing their fetched provenance.
- [**search**](search/index.md) – Find visible passages by full-text search, vector search, or both.
- [**source_status**](source_status/index.md) – Read the committed lifecycle and index state of a document source.

**Functions:**

- [**check_citations**](citation/check_citations.md) – Return one verdict for each cited evidence id, in the order given.
- [**entity_search**](entities/entity_search.md) – Find up to `limit` entities that match a query by name or by meaning.
- [**explore_relationships**](entities/explore_relationships.md) – Explore the entity relations around one entity, within bounds.
- [**fetch_evidence**](fetch/fetch_evidence.md) – Return the text of each evidence id, in the order given.
- [**navigate_document_tree**](navigate/navigate_document_tree.md) – Return the passages that one relation reaches from an evidence id.
- [**render_citations**](render/render_citations.md) – Replace validated inline IDs with numbered citations and a source list.
- [**search_evidence**](search/search_evidence.md) – Find up to `limit` visible passages that match a query.
