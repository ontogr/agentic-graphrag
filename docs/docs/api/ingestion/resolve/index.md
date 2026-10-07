---
title: agrag.ingestion.resolve
sidebar_label: resolve
---

# `agrag.ingestion.resolve` \{#agrag-ingestion-resolve}

Entity resolution public API.

**Modules:**

- [**batch_validation**](batch_validation/index.md) – Validation for LLM batch entity-match verdicts.
- [**candidate_source**](candidate_source/index.md) – Candidate generation for in-batch and persisted graph entities.
- [**comparators**](comparators/index.md) – Comparison strategies used by entity resolution.
- [**exact_groups**](exact_groups/index.md) – Exact-name grouping for permanent raw entity records.
- [**resolution**](resolution/index.md) – Resolve mentions and persisted entities against the graph.
- [**resolver**](resolver/index.md) – Entity resolution: deciding which ExtractedEntity mentions are the same thing.
- [**zone_classifier**](zone_classifier/index.md) – Zone classification for entity-resolution candidate pairs.

**Classes:**

- [**BatchResolution**](BatchResolution.md) – The outcome of resolving one batch of mentions.
- [**CandidateSource**](CandidateSource.md) – Narrows which in-batch entity pairs resolution compares.
- [**Comparator**](Comparator.md) – One matching strategy a Resolver runs against a candidate pair.
- [**ComparisonResult**](ComparisonResult.md) – The verdict and evidence produced by one comparator.
- [**ComparisonVerdict**](ComparisonVerdict.md) – A Comparator's verdict on one entity pair.
- [**ExactMatch**](ExactMatch.md) – Matches when normalized text is identical. Never returns NO_MATCH.
- [**FuzzyMatch**](FuzzyMatch.md) – Fast-path accepter for near-identical names. Never returns NO_MATCH.
- [**GraphCandidateSource**](GraphCandidateSource.md) – Blocks by label in-batch; ANN-searches persisted entities globally.
- [**LLMVerify**](LLMVerify.md) – Asks an LLM to verify an ambiguous pair. Last resort; never UNCERTAIN.
- [**PersistedCandidateSource**](PersistedCandidateSource.md) – Supplies only candidate pairs between new mentions and raw graph entities.
- [**ResolutionGroup**](ResolutionGroup.md) – One set of ExtractedEntity indices resolution decided are the same entity.
- [**ResolutionResult**](ResolutionResult.md) – The groups, non-exact evidence, and ambiguity count of one pass.
- [**ResolvedMatch**](ResolvedMatch.md) – One confirmed non-exact match between two input entity indices.
- [**Resolver**](Resolver-ref.md) – Routes blocked candidate pairs through exact, fuzzy, embedding, and LLM zones.

**Functions:**

- [**build_relation_neighbors**](build_relation_neighbors.md) – Build LLMVerify neighbor context from one batch's extracted relations.
- [**exact_resolution_groups**](exact_resolution_groups.md) – Group mentions only when they share exact raw-entity identity.
- [**fetch_persisted_neighbors**](fetch_persisted_neighbors.md) – Fetch a bounded neighbor-relationship sample for persisted entities.
- [**find_exact_matches**](find_exact_matches.md) – Return each mention index's matching persisted Entity, if it has one.
- [**persisted_candidate_indices**](persisted_candidate_indices.md) – Return ANN candidate indices, with a bounded exhaustive fallback.
- [**resolve_among**](resolve_among.md) – Resolve a fixed set of persisted entities by comparing same-label pairs.
- [**resolve_batch**](resolve_batch.md) – Resolve one extraction batch against itself and the persisted graph.
- [**resolve_persisted**](resolve_persisted.md) – Resolve persisted entities against each other.

**Attributes:**

- [**SYSTEM_RELATION_TYPES**](SYSTEM_RELATION_TYPES.md) –
