---
title: agrag.ingestion.resolve.candidate_source
sidebar_label: candidate_source
---

# `agrag.ingestion.resolve.candidate_source` \{#agrag-ingestion-resolve-candidate_source}

Candidate generation for in-batch and persisted graph entities.

**Classes:**

- [**CandidateSource**](CandidateSource.md) – Narrows which in-batch entity pairs resolution compares.
- [**GraphCandidateSource**](GraphCandidateSource.md) – Blocks by label in-batch; ANN-searches persisted entities globally.
- [**PersistedCandidateSource**](PersistedCandidateSource.md) – Supplies only candidate pairs between new mentions and raw graph entities.

**Functions:**

- [**build_relation_neighbors**](build_relation_neighbors.md) – Build LLMVerify neighbor context from one batch's extracted relations.
- [**exact_match_lookup**](exact_match_lookup.md) – Return persisted exact matches, including resolved tombstone aliases.
- [**fetch_persisted_neighbors**](fetch_persisted_neighbors.md) – Fetch a bounded neighbor-relationship sample for persisted entities.
- [**persisted_candidate_indices**](persisted_candidate_indices.md) – Return ANN candidate indices, with a bounded exhaustive fallback.

**Attributes:**

- [**MAX_NEIGHBORS_PER_ENTITY**](MAX_NEIGHBORS_PER_ENTITY.md) –
