---
title: agrag.ingestion.resolve.resolver
sidebar_label: resolver
---

# `agrag.ingestion.resolve.resolver` \{#agrag-ingestion-resolve-resolver}

Entity resolution: deciding which ExtractedEntity mentions are the same thing.

**Classes:**

- [**Comparator**](../comparators/Comparator.md) – One matching strategy a Resolver runs against a candidate pair.
- [**ComparisonResult**](../comparators/ComparisonResult.md) – The verdict and evidence produced by one comparator.
- [**ComparisonVerdict**](../comparators/ComparisonVerdict.md) – A Comparator's verdict on one entity pair.
- [**ExactMatch**](../comparators/ExactMatch.md) – Matches when normalized text is identical. Never returns NO_MATCH.
- [**FuzzyMatch**](../comparators/FuzzyMatch.md) – Fast-path accepter for near-identical names. Never returns NO_MATCH.
- [**LLMVerify**](../comparators/LLMVerify.md) – Asks an LLM to verify an ambiguous pair. Last resort; never UNCERTAIN.
- [**ResolutionGroup**](ResolutionGroup.md) – One set of ExtractedEntity indices resolution decided are the same entity.
- [**ResolutionResult**](ResolutionResult.md) – The groups, non-exact evidence, and ambiguity count of one pass.
- [**ResolvedMatch**](ResolvedMatch.md) – One confirmed non-exact match between two input entity indices.
- [**Resolver**](Resolver-ref.md) – Routes blocked candidate pairs through exact, fuzzy, embedding, and LLM zones.

**Attributes:**

- [**logger**](../../../retrieval/retrievers/text2cypher/logger.md) –
