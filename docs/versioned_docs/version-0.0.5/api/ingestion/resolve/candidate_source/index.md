---
title: agrag.ingestion.resolve.candidate_source
sidebar_label: candidate_source
---

# `agrag.ingestion.resolve.candidate_source` \{#agrag-ingestion-resolve-candidate_source}

Candidate generation for in-batch and persisted graph entities.

**Classes:**

- [**CandidateSource**](CandidateSource.md) – Narrows which in-batch entity pairs resolution compares.
- [**GraphCandidateSource**](GraphCandidateSource.md) – Block by label in-batch. Search persisted entities globally with ANN.
- [**PersistedCandidateSource**](PersistedCandidateSource.md) – Supplies only candidate pairs between new mentions and raw graph entities.

**Functions:**

- [**build_relation_neighbors**](build_relation_neighbors.md) – Build LLMVerify neighbor context from one batch's extracted relations.
- [**fetch_persisted_neighbors**](fetch_persisted_neighbors.md) – Fetch a bounded neighbor-relationship sample for persisted entities.
- [**persisted_candidate_indices**](persisted_candidate_indices.md) – Return ANN candidate indices, with a bounded exhaustive fallback.
- [**read_candidates**](read_candidates.md) – Read the persisted candidates for one mention, or report the failure.

**Attributes:**

- [**MAX_NEIGHBORS_PER_ENTITY**](MAX_NEIGHBORS_PER_ENTITY.md) –
