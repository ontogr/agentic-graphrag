---
title: agrag.evidence
sidebar_position: 13
---


# `agrag.evidence` \{#agrag-evidence}

Evidence discovery, exact fetch and citation checks over Document text.

The functions take a graph store and enforce the caller's document scope inside
their queries. Evidence ids name passage text of one version of a document.

**Modules:**

- [**citation**](citation/index.md) – Check that cited evidence ids trace to evidence the caller fetched.
- [**discover**](discover/index.md) – Find visible passages by full-text search, vector search, or both.
- [**fetch**](fetch/index.md) – Fetch the exact text behind evidence ids, limited to the caller's scope.
- [**ids**](ids/index.md) – Encode and decode evidence ids.
- [**source_status**](source_status/index.md) – Read the committed lifecycle and index state of a document source.

**Functions:**

- [**check_citations**](citation/check_citations.md) – Return one verdict for each cited evidence id, in the order given.
