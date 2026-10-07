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

- [**BatchResolution**](resolution/BatchResolution.md) – The outcome of resolving one batch of mentions.
- [**CandidateSource**](candidate_source/CandidateSource.md) – Narrows which in-batch entity pairs resolution compares.
- [**Comparator**](comparators/Comparator.md) – One matching strategy a Resolver runs against a candidate pair.
- [**ComparisonResult**](comparators/ComparisonResult.md) – The verdict and evidence produced by one comparator.
- [**ComparisonVerdict**](comparators/ComparisonVerdict.md) – A Comparator's verdict on one entity pair.
- [**ExactMatch**](comparators/ExactMatch.md) – Matches when normalized text is identical. Never returns NO_MATCH.
- [**FuzzyMatch**](comparators/FuzzyMatch.md) – Fast-path accepter for near-identical names. Never returns NO_MATCH.
- [**GraphCandidateSource**](candidate_source/GraphCandidateSource.md) – Block by label in-batch. Search persisted entities globally with ANN.
- [**LLMVerify**](comparators/LLMVerify.md) – Ask an LLM to verify an ambiguous pair. Last resort. Never UNCERTAIN.
- [**PersistedCandidateSource**](candidate_source/PersistedCandidateSource.md) – Supplies only candidate pairs between new mentions and raw graph entities.
- [**ResolutionGroup**](resolver/ResolutionGroup.md) – One set of ExtractedEntity indices resolution decided are the same entity.
- [**ResolutionResult**](resolver/ResolutionResult.md) – The groups, non-exact evidence, and ambiguity count of one pass.
- [**ResolvedMatch**](resolver/ResolvedMatch.md) – One confirmed non-exact match between two input entity indices.
- [**Resolver**](resolver/Resolver-ref.md) – Routes blocked candidate pairs through exact, fuzzy, embedding, and LLM zones.

**Functions:**

- [**build_relation_neighbors**](candidate_source/build_relation_neighbors.md) – Build LLMVerify neighbor context from one batch's extracted relations.
- [**exact_resolution_groups**](exact_groups/exact_resolution_groups.md) – Group mentions only when they share exact raw-entity identity.
- [**fetch_persisted_neighbors**](candidate_source/fetch_persisted_neighbors.md) – Fetch a bounded neighbor-relationship sample for persisted entities.
- [**find_exact_matches**](resolution/find_exact_matches.md) – Return each mention index's matching persisted Entity, if it has one.
- [**persisted_candidate_indices**](candidate_source/persisted_candidate_indices.md) – Return ANN candidate indices, with a bounded exhaustive fallback.
- [**resolve_among**](resolution/resolve_among.md) – Resolve a fixed set of persisted entities by comparing same-label pairs.
- [**resolve_batch**](resolution/resolve_batch.md) – Resolve one extraction batch against itself and the persisted graph.
- [**resolve_persisted**](resolution/resolve_persisted.md) – Resolve persisted entities against each other.

**Attributes:**

- [**SYSTEM_RELATION_TYPES**](resolution/SYSTEM_RELATION_TYPES.md) –
